"""Realtime presence tracking, configurable non-punitive incident workflow, and teacher actions."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.db.locks import EXAM_WRITE_LOCK
from app.db.models import (
    AnswerRevision,
    Attempt,
    DeviceBinding,
    Exam,
    ExamQuestion,
    Incident,
    PresenceEvent,
    Student,
    Submission,
)
from app.security.auth import StudentPrincipal, sign_token
from app.services.audit_service import record_audit_event
from app.services.exam_service import compute_remaining_seconds, ensure_aware
from app.services.roster_service import list_classroom_students
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_MONITORING_POLICY: dict[str, int] = {
    "heartbeat_s": 3,
    "suspected_s": 5,
    "disconnect_s": 15,
    "lock_after_s": 30,
    "grace_submit_s": 30,
}

ALLOWED_CLIENT_SIGNAL_TYPES = {
    "APP_HIDDEN",
    "PAGE_UNLOADED",
    "NETWORK_LOST",
    "CLIENT_RELOAD",
}


def parse_exam_policy(exam: Exam) -> dict[str, int]:
    """Parse exam monitoring thresholds with safe defaults."""
    policy = dict(DEFAULT_MONITORING_POLICY)
    try:
        raw = json.loads(exam.policy_json or "{}")
        if isinstance(raw, dict):
            for key in DEFAULT_MONITORING_POLICY:
                if key in raw and isinstance(raw[key], int | float):
                    policy[key] = max(0, int(raw[key]))
    except Exception:
        pass
    if policy["heartbeat_s"] < 1:
        policy["heartbeat_s"] = 3
    if policy["suspected_s"] < policy["heartbeat_s"]:
        policy["suspected_s"] = max(5, policy["heartbeat_s"] + 2)
    if policy["disconnect_s"] < policy["suspected_s"]:
        policy["disconnect_s"] = max(15, policy["suspected_s"] + 5)
    if policy["lock_after_s"] > 0 and policy["lock_after_s"] < policy["disconnect_s"]:
        policy["lock_after_s"] = policy["disconnect_s"]
    return policy


def _sanitize_signal_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if not details:
        return {}
    clean: dict[str, Any] = {}
    for idx, (k, v) in enumerate(details.items()):
        if idx >= 8:
            break
        key = str(k)[:48]
        if isinstance(v, bool | int | float):
            clean[key] = v
        elif isinstance(v, str):
            clean[key] = v[:120]
    return clean


def _validate_student_ownership(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
) -> tuple[Attempt, Exam]:
    if attempt_id != student.attempt_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập phiên của học sinh khác.",
        )
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi.")
    if attempt.session_id != student.session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên thiết bị đã bị giáo viên đặt lại hoặc thay thế.",
        )
    exam = db.get(Exam, attempt.exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    return attempt, exam


def update_exam_policy(
    db: Session,
    *,
    exam_id: str,
    heartbeat_s: int,
    suspected_s: int,
    disconnect_s: int,
    lock_after_s: int,
    grace_submit_s: int,
    teacher_id: int,
) -> dict[str, int]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    if not (1 <= heartbeat_s <= 30):
        raise HTTPException(status_code=400, detail="Nhịp heartbeat phải nằm trong khoảng 1–30 giây.")
    if suspected_s < heartbeat_s:
        raise HTTPException(status_code=400, detail="Ngưỡng nghi mất tín hiệu phải >= chu kỳ heartbeat.")
    if disconnect_s < suspected_s:
        raise HTTPException(status_code=400, detail="Ngưỡng mất kết nối phải >= ngưỡng nghi mất.")
    if lock_after_s != 0 and lock_after_s < disconnect_s:
        raise HTTPException(
            status_code=400,
            detail="Ngưỡng tự tạm khóa phải bằng 0 (tắt) hoặc >= ngưỡng mất kết nối.",
        )

    new_policy = {
        "heartbeat_s": int(heartbeat_s),
        "suspected_s": int(suspected_s),
        "disconnect_s": int(disconnect_s),
        "lock_after_s": int(lock_after_s),
        "grace_submit_s": max(0, min(300, int(grace_submit_s))),
    }
    exam.policy_json = json.dumps(new_policy)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="UPDATE_MONITORING_POLICY",
        target_type="exam",
        target_id=exam.id,
        details=new_policy,
    )
    db.commit()
    return new_policy


def record_student_heartbeat(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Update last heartbeat timestamp & recover presence if healthy (never unlocks teacher/incident lock)."""
    ts = now or datetime.now(UTC)
    with EXAM_WRITE_LOCK:
        attempt, exam = _validate_student_ownership(db, attempt_id=attempt_id, student=student)
        policy = parse_exam_policy(exam)
        prev_presence = attempt.presence_state
        state_changed = False

        attempt.last_seen = ts
        attempt.last_heartbeat_at = ts

        if attempt.state in {"READY", "ACTIVE"}:
            if prev_presence == "DISCONNECTED":
                attempt.reconnect_count += 1
                db.add(
                    PresenceEvent(
                        id=str(uuid.uuid4()),
                        exam_id=exam.id,
                        attempt_id=attempt.id,
                        event_type="RECONNECTED",
                        server_time=ts,
                        details_json=json.dumps({"previous_state": prev_presence}),
                    )
                )
                state_changed = True
            elif prev_presence != "ACTIVE":
                if prev_presence == "OFFLINE":
                    db.add(
                        PresenceEvent(
                            id=str(uuid.uuid4()),
                            exam_id=exam.id,
                            attempt_id=attempt.id,
                            event_type="ACTIVE",
                            server_time=ts,
                            details_json="{}",
                        )
                    )
                state_changed = True
            attempt.presence_state = "ACTIVE"

        db.commit()
        open_inc = db.execute(
            select(Incident)
            .where(Incident.attempt_id == attempt.id, Incident.state == "OPEN")
            .order_by(Incident.opened_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        return {
            "attempt_id": attempt.id,
            "exam_id": exam.id,
            "exam_status": exam.status,
            "is_paused": exam.paused_at is not None,
            "attempt_state": attempt.state,
            "presence_state": attempt.presence_state,
            "remaining_s": compute_remaining_seconds(exam, attempt, ts),
            "extra_time_s": attempt.extra_time_s,
            "server_time_utc": ts.isoformat(),
            "heartbeat_s": policy["heartbeat_s"],
            "incident_reason": open_inc.summary if open_inc else None,
            "state_changed": state_changed,
        }


def record_student_client_event(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
    event_type: str,
    details: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> PresenceEvent:
    """Record client visibility/pagehide/network/reload signals neutrally without accusing misconduct."""
    clean_type = event_type.strip().upper()
    if clean_type not in ALLOWED_CLIENT_SIGNAL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Loại tín hiệu giám sát không hợp lệ: {clean_type}",
        )

    ts = now or datetime.now(UTC)
    clean_details = _sanitize_signal_details(details)
    with EXAM_WRITE_LOCK:
        attempt, exam = _validate_student_ownership(db, attempt_id=attempt_id, student=student)
        if attempt.state in {"SUBMITTED", "ENDED_WITH_REVIEW"}:
            # Post-submit page unload or close is harmless noise; acknowledge without mutation
            ev = PresenceEvent(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                attempt_id=attempt.id,
                event_type=clean_type,
                server_time=ts,
                details_json=json.dumps({**clean_details, "ignored_after_end": True}),
            )
            db.add(ev)
            db.commit()
            return ev

        attempt.last_seen = ts
        if clean_type in {"APP_HIDDEN", "PAGE_UNLOADED"} and exam.status == "RUNNING":
            attempt.hidden_event_count += 1
        elif clean_type == "CLIENT_RELOAD":
            attempt.reconnect_count += 1

        ev = PresenceEvent(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            attempt_id=attempt.id,
            event_type=clean_type,
            server_time=ts,
            details_json=json.dumps(clean_details, ensure_ascii=False),
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return ev


def evaluate_room_presence(
    db: Session,
    *,
    exam_id: str,
    now: datetime | None = None,
) -> bool:
    """Evaluate elapsed silence against configurable policy; returns True if any state transitioned."""
    ts = now or datetime.now(UTC)
    with EXAM_WRITE_LOCK:
        exam = db.get(Exam, exam_id)
        if exam is None or exam.status != "RUNNING" or exam.paused_at is not None:
            return False

        policy = parse_exam_policy(exam)
        suspected_s = policy["suspected_s"]
        disconnect_s = policy["disconnect_s"]
        lock_after_s = policy["lock_after_s"]

        attempts = (
            db.execute(
                select(Attempt).where(
                    Attempt.exam_id == exam.id,
                    Attempt.state == "ACTIVE",
                )
            )
            .scalars()
            .all()
        )

        changed = False
        for att in attempts:
            ref_ts = att.last_heartbeat_at or att.started_at or att.created_at
            silence_s = max(0.0, (ts - ensure_aware(ref_ts)).total_seconds())

            if lock_after_s > 0 and silence_s >= lock_after_s:
                att.presence_state = "DISCONNECTED"
                att.state = "LOCKED_PENDING_REVIEW"
                db.add(
                    PresenceEvent(
                        id=str(uuid.uuid4()),
                        exam_id=exam.id,
                        attempt_id=att.id,
                        event_type="HEARTBEAT_TIMEOUT",
                        server_time=ts,
                        details_json=json.dumps({"silence_s": round(silence_s, 1)}),
                    )
                )
                db.add(
                    PresenceEvent(
                        id=str(uuid.uuid4()),
                        exam_id=exam.id,
                        attempt_id=att.id,
                        event_type="LOCKED_PENDING_REVIEW",
                        server_time=ts,
                        details_json=json.dumps({"lock_after_s": lock_after_s}),
                    )
                )
                existing_open = db.execute(
                    select(Incident).where(
                        Incident.attempt_id == att.id,
                        Incident.state == "OPEN",
                    )
                ).scalar_one_or_none()
                if existing_open is None:
                    db.add(
                        Incident(
                            id=str(uuid.uuid4()),
                            exam_id=exam.id,
                            attempt_id=att.id,
                            state="OPEN",
                            trigger_type="HEARTBEAT_TIMEOUT",
                            summary=(
                                f"Mất tín hiệu kết nối {int(silence_s)} giây "
                                f"(vượt ngưỡng {lock_after_s}s). Cần giáo viên xác minh kỹ thuật."
                            ),
                            opened_at=ts,
                        )
                    )
                changed = True
            elif silence_s >= disconnect_s and att.presence_state != "DISCONNECTED":
                att.presence_state = "DISCONNECTED"
                db.add(
                    PresenceEvent(
                        id=str(uuid.uuid4()),
                        exam_id=exam.id,
                        attempt_id=att.id,
                        event_type="HEARTBEAT_TIMEOUT",
                        server_time=ts,
                        details_json=json.dumps({"silence_s": round(silence_s, 1)}),
                    )
                )
                changed = True
            elif silence_s >= suspected_s and att.presence_state == "ACTIVE":
                att.presence_state = "SUSPECTED"
                db.add(
                    PresenceEvent(
                        id=str(uuid.uuid4()),
                        exam_id=exam.id,
                        attempt_id=att.id,
                        event_type="HEARTBEAT_SUSPECTED",
                        server_time=ts,
                        details_json=json.dumps({"silence_s": round(silence_s, 1)}),
                    )
                )
                changed = True

        if changed:
            db.commit()
        return changed


def lock_attempt_for_review(
    db: Session,
    *,
    exam_id: str,
    attempt_id: str,
    reason: str,
    teacher_id: int,
) -> tuple[Attempt, Incident]:
    clean_reason = reason.strip()
    if len(clean_reason) < 3:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập lý do khóa tạm bài thi (>= 3 ký tự).",
        )
    ts = datetime.now(UTC)
    with EXAM_WRITE_LOCK:
        attempt = db.get(Attempt, attempt_id)
        if attempt is None or attempt.exam_id != exam_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm bài.")
        if attempt.state in {"SUBMITTED", "ENDED_WITH_REVIEW"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phiên làm bài đã kết thúc hoặc đã nộp.",
            )

        attempt.state = "LOCKED_PENDING_REVIEW"
        incident = Incident(
            id=str(uuid.uuid4()),
            exam_id=exam_id,
            attempt_id=attempt.id,
            state="OPEN",
            trigger_type="TEACHER_MANUAL_LOCK",
            summary=clean_reason[:240],
            opened_at=ts,
        )
        db.add(incident)
        db.add(
            PresenceEvent(
                id=str(uuid.uuid4()),
                exam_id=exam_id,
                attempt_id=attempt.id,
                event_type="TEACHER_MANUAL_LOCK",
                server_time=ts,
                details_json=json.dumps({"reason": clean_reason}, ensure_ascii=False),
            )
        )
        record_audit_event(
            db,
            actor_type="teacher",
            actor_id=str(teacher_id),
            action="LOCK_ATTEMPT_FOR_REVIEW",
            target_type="attempt",
            target_id=attempt.id,
            details={"exam_id": exam_id, "reason": clean_reason},
        )
        db.commit()
        db.refresh(attempt)
        db.refresh(incident)
        return attempt, incident


def resolve_attempt_incident(
    db: Session,
    *,
    exam_id: str,
    attempt_id: str,
    action: str,
    reason: str,
    extend_minutes: int,
    teacher_id: int,
) -> dict[str, Any]:
    clean_action = action.strip().lower()
    if clean_action not in {"unlock", "extend_time", "terminate"}:
        raise HTTPException(status_code=400, detail="Thao tác xử lý sự cố không hợp lệ.")
    clean_reason = reason.strip()
    if len(clean_reason) < 3:
        raise HTTPException(status_code=400, detail="Vui lòng nhập lý do xử lý (>= 3 ký tự).")
    if clean_action == "extend_time" and not (1 <= extend_minutes <= 60):
        raise HTTPException(status_code=400, detail="Số phút gia hạn phải từ 1 đến 60 phút.")

    ts = datetime.now(UTC)
    with EXAM_WRITE_LOCK:
        exam = db.get(Exam, exam_id)
        attempt = db.get(Attempt, attempt_id)
        if exam is None or attempt is None or attempt.exam_id != exam_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm bài hoặc kỳ thi.")
        if attempt.state in {"SUBMITTED", "ENDED_WITH_REVIEW"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bài thi của học sinh đã kết thúc hoặc đã nộp.",
            )

        open_incidents = (
            db.execute(
                select(Incident).where(
                    Incident.attempt_id == attempt.id,
                    Incident.state == "OPEN",
                )
            )
            .scalars()
            .all()
        )

        if clean_action == "unlock":
            attempt.state = "ACTIVE" if exam.status == "RUNNING" else "READY"
            attempt.presence_state = "ACTIVE" if exam.status == "RUNNING" else "OFFLINE"
            attempt.last_seen = ts
            attempt.last_heartbeat_at = ts
            inc_state = "RESOLVED_UNLOCKED"
            ev_type = "TEACHER_UNLOCK"
            audit_action = "RESOLVE_INCIDENT_UNLOCK"
        elif clean_action == "extend_time":
            attempt.extra_time_s += int(extend_minutes) * 60
            attempt.state = "ACTIVE" if exam.status == "RUNNING" else "READY"
            attempt.presence_state = "ACTIVE" if exam.status == "RUNNING" else "OFFLINE"
            attempt.last_seen = ts
            attempt.last_heartbeat_at = ts
            inc_state = "RESOLVED_EXTENDED"
            ev_type = "TEACHER_EXTEND_TIME"
            audit_action = "RESOLVE_INCIDENT_EXTEND_TIME"
        else:
            # Terminate preserves any already-ACKed answers into an immutable Submission snapshot
            existing_sub = db.execute(
                select(Submission).where(Submission.attempt_id == attempt.id)
            ).scalar_one_or_none()
            if existing_sub is None:
                revs = (
                    db.execute(
                        select(AnswerRevision)
                        .where(AnswerRevision.attempt_id == attempt.id)
                        .order_by(AnswerRevision.revision.asc(), AnswerRevision.committed_at.asc())
                    )
                    .scalars()
                    .all()
                )
                snapshot: dict[str, list[str]] = {}
                for r in revs:
                    snapshot[r.question_version_id] = list(json.loads(r.selected_option_ids_json))
                canon_json = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
                snap_hash = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()
                db.add(
                    Submission(
                        id=str(uuid.uuid4()),
                        attempt_id=attempt.id,
                        exam_id=exam.id,
                        student_id=attempt.student_id,
                        answer_snapshot_json=canon_json,
                        snapshot_hash=snap_hash,
                        submission_mode="teacher_terminate_review",
                        submitted_at=ts,
                    )
                )
            attempt.state = "ENDED_WITH_REVIEW"
            attempt.presence_state = "OFFLINE"
            attempt.submitted_at = attempt.submitted_at or ts
            inc_state = "RESOLVED_ENDED"
            ev_type = "TEACHER_TERMINATE"
            audit_action = "RESOLVE_INCIDENT_TERMINATE"

        for inc in open_incidents:
            inc.state = inc_state
            inc.resolved_at = ts
            inc.resolved_by = teacher_id
            inc.resolution_reason = clean_reason[:290]

        db.add(
            PresenceEvent(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                attempt_id=attempt.id,
                event_type=ev_type,
                server_time=ts,
                details_json=json.dumps(
                    {
                        "reason": clean_reason,
                        "extend_minutes": extend_minutes if clean_action == "extend_time" else 0,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        record_audit_event(
            db,
            actor_type="teacher",
            actor_id=str(teacher_id),
            action=audit_action,
            target_type="attempt",
            target_id=attempt.id,
            details={
                "exam_id": exam.id,
                "reason": clean_reason,
                "extra_time_s": attempt.extra_time_s,
                "resolved_incidents": len(open_incidents),
            },
        )
        db.commit()
        db.refresh(attempt)

        return {
            "attempt_id": attempt.id,
            "exam_id": exam.id,
            "attempt_state": attempt.state,
            "presence_state": attempt.presence_state,
            "extra_time_s": attempt.extra_time_s,
            "remaining_s": compute_remaining_seconds(exam, attempt, ts),
            "incident_state": inc_state,
        }


def refresh_student_token(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
    server_secret: bytes,
) -> tuple[str, int]:
    attempt, exam = _validate_student_ownership(db, attempt_id=attempt_id, student=student)
    if exam.status not in {"WAITING", "RUNNING"}:
        raise HTTPException(status_code=409, detail="Kỳ thi đã kết thúc, không cấp lại token phiên thi.")
    if attempt.state == "ENDED_WITH_REVIEW":
        raise HTTPException(status_code=403, detail="Phiên làm bài đã bị kết thúc bởi giáo viên.")

    active_binding = db.execute(
        select(DeviceBinding).where(
            DeviceBinding.attempt_id == attempt.id,
            DeviceBinding.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if active_binding is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiết bị đã bị đặt lại; vui lòng đăng nhập lại bằng mã tham gia.",
        )

    ttl_seconds = 7200
    token = sign_token(
        {
            "role": "student",
            "attempt_id": attempt.id,
            "exam_id": exam.id,
            "student_id": attempt.student_id,
            "session_id": attempt.session_id,
        },
        server_secret,
        ttl_seconds=ttl_seconds,
    )
    attempt.last_seen = datetime.now(UTC)
    db.commit()
    return token, ttl_seconds


def get_room_monitoring_snapshot(
    db: Session,
    *,
    exam_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate timeouts & assemble live monitoring summary for teacher console."""
    ts = now or datetime.now(UTC)
    evaluate_room_presence(db, exam_id=exam_id, now=ts)

    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")

    policy = parse_exam_policy(exam)
    students = list_classroom_students(db, classroom_id=exam.classroom_id)
    attempts = {
        a.student_id: a
        for a in db.execute(select(Attempt).where(Attempt.exam_id == exam_id)).scalars().all()
    }
    bound_attempt_ids = set(
        db.execute(
            select(DeviceBinding.attempt_id).where(
                DeviceBinding.exam_id == exam_id,
                DeviceBinding.revoked_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    open_incidents = (
        db.execute(
            select(Incident)
            .where(Incident.exam_id == exam_id, Incident.state == "OPEN")
            .order_by(Incident.opened_at.desc())
        )
        .scalars()
        .all()
    )
    open_incident_by_attempt = {inc.attempt_id: inc for inc in open_incidents}

    q_count = int(
        db.execute(
            select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
        ).scalar_one()
    )
    attempt_ids = [a.id for a in attempts.values()]
    answered_counts: dict[str, int] = {}
    if attempt_ids:
        rows = db.execute(
            select(
                AnswerRevision.attempt_id,
                func.count(func.distinct(AnswerRevision.question_version_id)),
            )
            .where(AnswerRevision.attempt_id.in_(attempt_ids))
            .group_by(AnswerRevision.attempt_id)
        ).all()
        answered_counts = {att_id: int(cnt) for att_id, cnt in rows}

    entries: list[dict[str, Any]] = []
    active_cnt = submitted_cnt = pending_cnt = suspected_cnt = disconnected_cnt = locked_cnt = 0

    for st in students:
        att = attempts.get(st.id)
        inc = open_incident_by_attempt.get(att.id) if att else None
        if att:
            if att.state == "SUBMITTED":
                submitted_cnt += 1
            elif att.state == "PENDING_APPROVAL":
                pending_cnt += 1
            elif att.state == "LOCKED_PENDING_REVIEW":
                locked_cnt += 1
            elif att.state == "ACTIVE":
                active_cnt += 1

            if att.state == "ACTIVE" and att.presence_state == "SUSPECTED":
                suspected_cnt += 1
            elif att.state in {"ACTIVE", "LOCKED_PENDING_REVIEW"} and att.presence_state == "DISCONNECTED":
                disconnected_cnt += 1

        hb_age_s: int | None = None
        if att and att.last_heartbeat_at is not None:
            hb_age_s = max(0, int((ts - ensure_aware(att.last_heartbeat_at)).total_seconds()))

        entries.append(
            {
                "student_id": st.id,
                "roster_code": st.roster_code,
                "full_name": st.full_name,
                "attempt_id": att.id if att else None,
                "attempt_state": att.state if att else "NOT_JOINED",
                "presence_state": att.presence_state if att else "OFFLINE",
                "device_bound": (att is not None and att.id in bound_attempt_ids),
                "latest_revision": att.latest_revision if att else 0,
                "answered_count": answered_counts.get(att.id, 0) if att else 0,
                "last_heartbeat_at": att.last_heartbeat_at.isoformat()
                if (att and att.last_heartbeat_at)
                else None,
                "heartbeat_age_s": hb_age_s,
                "reconnect_count": att.reconnect_count if att else 0,
                "hidden_event_count": att.hidden_event_count if att else 0,
                "extra_time_s": att.extra_time_s if att else 0,
                "open_incident_id": inc.id if inc else None,
                "open_incident_summary": inc.summary if inc else None,
                "submitted_at": att.submitted_at.isoformat() if (att and att.submitted_at) else None,
            }
        )

    student_by_attempt = {
        att.id: db.get(Student, att.student_id)
        for att in attempts.values()
    }
    incidents_payload = []
    for inc in open_incidents:
        st_obj = student_by_attempt.get(inc.attempt_id)
        incidents_payload.append(
            {
                "id": inc.id,
                "attempt_id": inc.attempt_id,
                "roster_code": st_obj.roster_code if st_obj else "",
                "full_name": st_obj.full_name if st_obj else "",
                "state": inc.state,
                "trigger_type": inc.trigger_type,
                "summary": inc.summary,
                "opened_at": inc.opened_at.isoformat(),
            }
        )

    return {
        "exam_id": exam.id,
        "room_code": exam.room_code,
        "title": exam.title,
        "status": exam.status,
        "is_paused": exam.paused_at is not None,
        "remaining_s": compute_remaining_seconds(exam, now=ts),
        "question_count": q_count,
        "server_time_utc": ts.isoformat(),
        "policy": policy,
        "summary": {
            "total_students": len(students),
            "active_count": active_cnt,
            "submitted_count": submitted_cnt,
            "pending_count": pending_cnt,
            "suspected_count": suspected_cnt,
            "disconnected_count": disconnected_cnt,
            "locked_count": locked_cnt,
            "open_incidents_count": len(open_incidents),
        },
        "open_incidents": incidents_payload,
        "roster": entries,
    }


def get_attempt_timeline(
    db: Session,
    *,
    exam_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm bài.")
    student = db.get(Student, attempt.student_id)
    events = (
        db.execute(
            select(PresenceEvent)
            .where(PresenceEvent.attempt_id == attempt_id)
            .order_by(PresenceEvent.server_time.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    incidents = (
        db.execute(
            select(Incident)
            .where(Incident.attempt_id == attempt_id)
            .order_by(Incident.opened_at.desc())
        )
        .scalars()
        .all()
    )
    return {
        "attempt_id": attempt.id,
        "exam_id": exam_id,
        "roster_code": student.roster_code if student else "",
        "full_name": student.full_name if student else "",
        "attempt_state": attempt.state,
        "presence_state": attempt.presence_state,
        "extra_time_s": attempt.extra_time_s,
        "reconnect_count": attempt.reconnect_count,
        "hidden_event_count": attempt.hidden_event_count,
        "events": [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "server_time": ensure_aware(ev.server_time).isoformat(),
                "details": json.loads(ev.details_json or "{}"),
            }
            for ev in events
        ],
        "incidents": [
            {
                "id": inc.id,
                "state": inc.state,
                "trigger_type": inc.trigger_type,
                "summary": inc.summary,
                "opened_at": ensure_aware(inc.opened_at).isoformat(),
                "resolved_at": ensure_aware(inc.resolved_at).isoformat() if inc.resolved_at else None,
                "resolution_reason": inc.resolution_reason,
            }
            for inc in incidents
        ],
    }
