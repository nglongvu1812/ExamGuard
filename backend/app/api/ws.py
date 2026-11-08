"""Authenticated WebSocket room hub with strict role & attempt isolation (zero early key leak)."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.db.models import Attempt, Exam
from app.security.auth import StudentPrincipal, verify_token
from app.services.exam_service import compute_remaining_seconds
from app.services.monitoring_service import (
    get_room_monitoring_snapshot,
    parse_exam_policy,
    record_student_client_event,
    record_student_heartbeat,
)
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, WebSocketException, status

router = APIRouter(tags=["websocket"])


class RoomConnectionManager:
    """Tracks live teacher & student WebSockets per exam_id cleanly."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._teacher_sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self._student_sockets: dict[str, dict[str, set[WebSocket]]] = defaultdict(
            lambda: defaultdict(set)
        )

    async def connect_teacher(self, exam_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._teacher_sockets[exam_id].add(ws)

    async def connect_student(self, exam_id: str, attempt_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._student_sockets[exam_id][attempt_id].add(ws)

    async def disconnect(
        self,
        exam_id: str,
        ws: WebSocket,
        *,
        attempt_id: str | None = None,
    ) -> None:
        async with self._lock:
            self._teacher_sockets[exam_id].discard(ws)
            if attempt_id is not None:
                sockets = self._student_sockets[exam_id].get(attempt_id)
                if sockets is not None:
                    sockets.discard(ws)
                    if not sockets:
                        self._student_sockets[exam_id].pop(attempt_id, None)

    async def broadcast_teacher_snapshot(self, exam_id: str, snapshot: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._teacher_sockets.get(exam_id, set()))
        payload = {"type": "room_snapshot", "snapshot": snapshot}
        stale: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._teacher_sockets[exam_id].discard(ws)

    async def send_to_attempt(self, exam_id: str, attempt_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._student_sockets.get(exam_id, {}).get(attempt_id, set()))
        stale: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        if stale:
            async with self._lock:
                sockets = self._student_sockets[exam_id].get(attempt_id)
                if sockets is not None:
                    for ws in stale:
                        sockets.discard(ws)

    async def broadcast_exam_state(self, exam_id: str, payload: dict[str, Any]) -> None:
        """Broadcast sanitized exam-level state change (never answer keys or peer data)."""
        async with self._lock:
            t_targets = list(self._teacher_sockets.get(exam_id, set()))
            s_groups = [
                (att_id, list(socks))
                for att_id, socks in self._student_sockets.get(exam_id, {}).items()
            ]
        for ws in t_targets:
            try:
                await ws.send_json(payload)
            except Exception:
                await self.disconnect(exam_id, ws)
        for att_id, socks in s_groups:
            for ws in socks:
                try:
                    await ws.send_json(payload)
                except Exception:
                    await self.disconnect(exam_id, ws, attempt_id=att_id)

    async def revoke_attempt_sockets(self, exam_id: str, attempt_id: str, reason: str) -> None:
        async with self._lock:
            targets = list(self._student_sockets.get(exam_id, {}).pop(attempt_id, set()))
        for ws in targets:
            try:
                await ws.send_json({"type": "session_revoked", "reason": reason})
                await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason[:100])
            except Exception:
                pass


def _extract_ws_token(websocket: WebSocket) -> str:
    token = websocket.query_params.get("token", "").strip()
    if token:
        return token
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


@router.websocket("/ws/v1/room/{exam_id}")
async def room_websocket(websocket: WebSocket, exam_id: str) -> None:
    token = _extract_ws_token(websocket)
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Thiếu mã xác thực.")

    secret: bytes = websocket.app.state.server_secret
    try:
        claims = verify_token(token, secret)
    except HTTPException as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Token không hợp lệ.") from exc

    role = claims.get("role")
    session_factory = websocket.app.state.session_factory
    ws_manager: RoomConnectionManager = websocket.app.state.ws_manager

    if role == "teacher":
        with session_factory() as db:
            exam = db.get(Exam, exam_id)
            if exam is None:
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Không tìm thấy kỳ thi.")
            snapshot = get_room_monitoring_snapshot(db, exam_id=exam_id)

        await websocket.accept()
        await ws_manager.connect_teacher(exam_id, websocket)
        try:
            await websocket.send_json(
                {
                    "type": "welcome",
                    "role": "teacher",
                    "exam_id": exam_id,
                    "snapshot": snapshot,
                }
            )
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "ping":
                    await websocket.send_json(
                        {"type": "pong", "server_time_utc": datetime.now(UTC).isoformat()}
                    )
                elif msg.get("type") == "request_snapshot":
                    with session_factory() as db:
                        snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
                    await websocket.send_json({"type": "room_snapshot", "snapshot": snap})
        except WebSocketDisconnect:
            pass
        finally:
            await ws_manager.disconnect(exam_id, websocket)
        return

    if role == "student":
        attempt_id = str(claims.get("attempt_id", ""))
        token_exam_id = str(claims.get("exam_id", ""))
        student_id = str(claims.get("student_id", ""))
        session_id = str(claims.get("session_id", ""))
        if token_exam_id != exam_id or not attempt_id or not student_id or not session_id:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Token không khớp phòng thi.",
            )

        principal = StudentPrincipal(
            attempt_id=attempt_id,
            exam_id=token_exam_id,
            student_id=student_id,
            session_id=session_id,
        )

        with session_factory() as db:
            att = db.get(Attempt, attempt_id)
            exam = db.get(Exam, exam_id)
            if (
                att is None
                or exam is None
                or att.exam_id != exam_id
                or att.student_id != student_id
                or att.session_id != session_id
                or att.state == "PENDING_APPROVAL"
            ):
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Phiên học sinh không hợp lệ hoặc chưa được duyệt.",
                )
            policy = parse_exam_policy(exam)
            welcome_payload = {
                "type": "welcome",
                "role": "student",
                "attempt_id": att.id,
                "exam_id": exam.id,
                "exam_status": exam.status,
                "attempt_state": att.state,
                "presence_state": att.presence_state,
                "is_paused": exam.paused_at is not None,
                "remaining_s": compute_remaining_seconds(exam, att),
                "extra_time_s": att.extra_time_s,
                "heartbeat_s": policy["heartbeat_s"],
                "server_time_utc": datetime.now(UTC).isoformat(),
            }

        await websocket.accept()
        await ws_manager.connect_student(exam_id, attempt_id, websocket)
        try:
            await websocket.send_json(welcome_payload)
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "ping":
                    await websocket.send_json(
                        {"type": "pong", "server_time_utc": datetime.now(UTC).isoformat()}
                    )
                elif mtype == "heartbeat":
                    try:
                        with session_factory() as db:
                            ack = record_student_heartbeat(
                                db, attempt_id=attempt_id, student=principal
                            )
                            room_snap: dict[str, Any] | None = (
                                get_room_monitoring_snapshot(db, exam_id=exam_id)
                                if ack["state_changed"]
                                else None
                            )
                        await websocket.send_json({"type": "heartbeat_ack", **ack})
                        if room_snap is not None:
                            await ws_manager.broadcast_teacher_snapshot(exam_id, room_snap)
                    except HTTPException as exc:
                        await websocket.send_json(
                            {"type": "auth_error", "detail": str(exc.detail)}
                        )
                        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                        return
                elif mtype == "client_event":
                    ev_name = str(msg.get("event_type", ""))
                    details = msg.get("details") if isinstance(msg.get("details"), dict) else {}
                    try:
                        with session_factory() as db:
                            ev = record_student_client_event(
                                db,
                                attempt_id=attempt_id,
                                student=principal,
                                event_type=ev_name,
                                details=details,
                            )
                            snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
                        await websocket.send_json(
                            {
                                "type": "event_ack",
                                "event_id": ev.id,
                                "event_type": ev.event_type,
                                "server_time_utc": ev.server_time.isoformat(),
                            }
                        )
                        await ws_manager.broadcast_teacher_snapshot(exam_id, snap)
                    except HTTPException as exc:
                        await websocket.send_json(
                            {"type": "error", "detail": str(exc.detail)}
                        )
        except WebSocketDisconnect:
            pass
        finally:
            await ws_manager.disconnect(exam_id, websocket, attempt_id=attempt_id)
        return

    raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Vai trò không hợp lệ.")
