"""Realtime monitoring REST API: policy config, presence/incidents, lock/unlock/extend/terminate, signals."""

from __future__ import annotations

from typing import Any, Literal

from app.api.deps import get_db
from app.security.auth import (
    StudentPrincipal,
    TeacherPrincipal,
    require_student,
    require_teacher,
)
from app.services.monitoring_service import (
    get_attempt_timeline,
    get_room_monitoring_snapshot,
    lock_attempt_for_review,
    record_student_client_event,
    record_student_heartbeat,
    refresh_student_token,
    resolve_attempt_incident,
    update_exam_policy,
)
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1", tags=["monitoring"])


class UpdatePolicyRequest(BaseModel):
    heartbeat_s: int = Field(default=3, ge=1, le=30)
    suspected_s: int = Field(default=5, ge=2, le=120)
    disconnect_s: int = Field(default=15, ge=5, le=300)
    lock_after_s: int = Field(default=30, ge=0, le=600)
    grace_submit_s: int = Field(default=30, ge=0, le=300)


class LockAttemptRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=250)


class ResolveIncidentRequest(BaseModel):
    action: Literal["unlock", "extend_time", "terminate"]
    reason: str = Field(min_length=3, max_length=300)
    extend_minutes: int = Field(default=5, ge=0, le=60)


class ClientSignalRequest(BaseModel):
    event_type: Literal["APP_HIDDEN", "PAGE_UNLOADED", "NETWORK_LOST", "CLIENT_RELOAD"]
    details: dict[str, Any] = Field(default_factory=dict)


class RefreshTokenResponse(BaseModel):
    attempt_token: str
    expires_in_s: int


# --- Teacher Monitoring Endpoints ---


@router.get("/monitoring/exams/{exam_id}")
def get_exam_monitoring(
    exam_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_room_monitoring_snapshot(db, exam_id=exam_id)


@router.patch("/monitoring/exams/{exam_id}/policy")
def patch_exam_monitoring_policy(
    exam_id: str,
    payload: UpdatePolicyRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return update_exam_policy(
        db,
        exam_id=exam_id,
        heartbeat_s=payload.heartbeat_s,
        suspected_s=payload.suspected_s,
        disconnect_s=payload.disconnect_s,
        lock_after_s=payload.lock_after_s,
        grace_submit_s=payload.grace_submit_s,
        teacher_id=teacher.teacher_id,
    )


@router.get("/monitoring/exams/{exam_id}/attempts/{attempt_id}/timeline")
def get_student_attempt_timeline(
    exam_id: str,
    attempt_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_attempt_timeline(db, exam_id=exam_id, attempt_id=attempt_id)


@router.post("/monitoring/exams/{exam_id}/attempts/{attempt_id}/lock")
async def post_lock_attempt(
    exam_id: str,
    attempt_id: str,
    payload: LockAttemptRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    attempt, incident = lock_attempt_for_review(
        db,
        exam_id=exam_id,
        attempt_id=attempt_id,
        reason=payload.reason,
        teacher_id=teacher.teacher_id,
    )
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.send_to_attempt(
            exam_id,
            attempt.id,
            {
                "type": "attempt_update",
                "attempt_id": attempt.id,
                "attempt_state": attempt.state,
                "presence_state": attempt.presence_state,
                "incident_reason": incident.summary,
            },
        )
        snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
        await ws_manager.broadcast_teacher_snapshot(exam_id, snap)
    return {
        "attempt_id": attempt.id,
        "attempt_state": attempt.state,
        "incident_id": incident.id,
    }


@router.post("/monitoring/exams/{exam_id}/attempts/{attempt_id}/resolve")
async def post_resolve_attempt_incident(
    exam_id: str,
    attempt_id: str,
    payload: ResolveIncidentRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    res = resolve_attempt_incident(
        db,
        exam_id=exam_id,
        attempt_id=attempt_id,
        action=payload.action,
        reason=payload.reason,
        extend_minutes=payload.extend_minutes if payload.action == "extend_time" else 0,
        teacher_id=teacher.teacher_id,
    )
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.send_to_attempt(
            exam_id,
            attempt_id,
            {"type": "attempt_update", **res},
        )
        snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
        await ws_manager.broadcast_teacher_snapshot(exam_id, snap)
    return res


# --- Student Telemetry, Fallback Heartbeat & Token Refresh ---


@router.post("/attempts/{attempt_id}/heartbeat")
async def post_student_heartbeat(
    attempt_id: str,
    request: Request,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ack = record_student_heartbeat(db, attempt_id=attempt_id, student=student)
    if ack.get("state_changed"):
        ws_manager = getattr(request.app.state, "ws_manager", None)
        if ws_manager is not None:
            snap = get_room_monitoring_snapshot(db, exam_id=student.exam_id)
            await ws_manager.broadcast_teacher_snapshot(student.exam_id, snap)
    return ack


@router.post("/attempts/{attempt_id}/events")
async def post_student_event(
    attempt_id: str,
    payload: ClientSignalRequest,
    request: Request,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ev = record_student_client_event(
        db,
        attempt_id=attempt_id,
        student=student,
        event_type=payload.event_type,
        details=payload.details,
    )
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        snap = get_room_monitoring_snapshot(db, exam_id=student.exam_id)
        await ws_manager.broadcast_teacher_snapshot(student.exam_id, snap)
    return {
        "event_id": ev.id,
        "event_type": ev.event_type,
        "server_time_utc": ev.server_time.isoformat(),
    }


@router.post("/attempts/{attempt_id}/refresh-token", response_model=RefreshTokenResponse)
def post_refresh_student_token(
    attempt_id: str,
    request: Request,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> RefreshTokenResponse:
    secret: bytes = request.app.state.server_secret
    token, ttl = refresh_student_token(
        db,
        attempt_id=attempt_id,
        student=student,
        server_secret=secret,
    )
    return RefreshTokenResponse(attempt_token=token, expires_in_s=ttl)
