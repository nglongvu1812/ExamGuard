"""Waiting room, hashed invite codes, student join, teacher approval, and device rebind."""

from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.models import (
    Attempt,
    ClassMembership,
    Classroom,
    DeviceBinding,
    Exam,
    PresenceEvent,
    Student,
    StudentInvite,
)
from app.security.auth import (
    INVITE_ALPHABET,
    generate_invite_code,
    hash_secret_value,
    sign_token,
    verify_secret_value,
)
from app.services.audit_service import record_audit_event
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _generate_room_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))


@dataclass(frozen=True)
class IssuedInviteDTO:
    student_id: str
    roster_code: str
    full_name: str
    invite_code: str
    expires_at: datetime


def create_waiting_room_session(
    db: Session,
    *,
    classroom_id: str,
    title: str,
    duration_s: int,
    invite_ttl_minutes: int,
    teacher_id: int,
    server_secret: bytes,
) -> tuple[Exam, list[IssuedInviteDTO]]:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None or classroom.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")

    room_code = _generate_room_code()
    while db.execute(select(Exam).where(Exam.room_code == room_code)).scalar_one_or_none():
        room_code = _generate_room_code()

    exam = Exam(
        id=str(uuid.uuid4()),
        classroom_id=classroom_id,
        room_code=room_code,
        title=title.strip() or f"Kiểm tra {classroom.name}",
        duration_s=max(60, duration_s),
        status="WAITING",
    )
    db.add(exam)
    db.flush()

    students = (
        db.execute(
            select(Student)
            .join(ClassMembership, ClassMembership.student_id == Student.id)
            .where(
                ClassMembership.classroom_id == classroom_id,
                ClassMembership.active_to.is_(None),
                Student.archived_at.is_(None),
            )
            .order_by(Student.roster_code.asc())
        )
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=max(5, invite_ttl_minutes))
    issued: list[IssuedInviteDTO] = []

    for st in students:
        plaintext_code = generate_invite_code(6)
        db.add(
            StudentInvite(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                student_id=st.id,
                code_hash=hash_secret_value(plaintext_code, server_secret),
                issued_at=now,
                expires_at=expires_at,
            )
        )
        issued.append(
            IssuedInviteDTO(
                student_id=st.id,
                roster_code=st.roster_code,
                full_name=st.full_name,
                invite_code=plaintext_code,
                expires_at=expires_at,
            )
        )

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="OPEN_WAITING_ROOM",
        target_type="exam",
        target_id=exam.id,
        details={"room_code": room_code, "student_count": len(issued)},
    )
    db.commit()
    db.refresh(exam)
    return exam, issued


def _ensure_aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


@dataclass(frozen=True)
class JoinRoomResult:
    attempt: Attempt
    student: Student
    exam: Exam
    attempt_token: str


def join_exam_room(
    db: Session,
    *,
    room_code: str,
    roster_code: str,
    invite_code: str,
    browser_key: str,
    user_agent: str,
    server_secret: bytes,
) -> JoinRoomResult:
    clean_room = room_code.strip().upper()
    clean_roster = roster_code.strip().upper()
    clean_invite = invite_code.strip().upper()
    clean_browser = browser_key.strip()

    if not clean_room or not clean_roster or not clean_invite or len(clean_browser) < 8:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập đầy đủ mã phòng, mã học sinh và mã tham gia hợp lệ.",
        )

    exam = db.execute(select(Exam).where(Exam.room_code == clean_room)).scalar_one_or_none()
    if exam is None or exam.status not in {"WAITING", "RUNNING"}:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phòng thi đang mở với mã này.",
        )

    student = db.execute(
        select(Student).where(Student.roster_code == clean_roster, Student.archived_at.is_(None))
    ).scalar_one_or_none()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã học sinh hoặc mã tham gia không chính xác.",
        )

    membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.classroom_id == exam.classroom_id,
            ClassMembership.student_id == student.id,
            ClassMembership.active_to.is_(None),
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Học sinh không thuộc danh sách lớp của phòng thi này.",
        )

    invites = (
        db.execute(
            select(StudentInvite)
            .where(
                StudentInvite.exam_id == exam.id,
                StudentInvite.student_id == student.id,
                StudentInvite.revoked_at.is_(None),
            )
            .order_by(StudentInvite.issued_at.desc())
        )
        .scalars()
        .all()
    )

    now = datetime.now(UTC)
    matched_invite: StudentInvite | None = None
    for inv in invites:
        if _ensure_aware(inv.expires_at) < now:
            continue
        if verify_secret_value(clean_invite, inv.code_hash, server_secret):
            matched_invite = inv
            break

    if matched_invite is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã tham gia không đúng hoặc đã hết hạn.",
        )

    browser_hash = hash_secret_value(clean_browser, server_secret)

    existing_attempt = db.execute(
        select(Attempt).where(Attempt.exam_id == exam.id, Attempt.student_id == student.id)
    ).scalar_one_or_none()

    if existing_attempt is not None:
        active_bindings = (
            db.execute(
                select(DeviceBinding).where(
                    DeviceBinding.attempt_id == existing_attempt.id,
                    DeviceBinding.revoked_at.is_(None),
                )
            )
            .scalars()
            .all()
        )
        if active_bindings:
            if any(b.device_token_hash == browser_hash for b in active_bindings):
                existing_attempt.last_seen = now
                db.commit()
                token = sign_token(
                    {
                        "role": "student",
                        "attempt_id": existing_attempt.id,
                        "exam_id": exam.id,
                        "student_id": student.id,
                        "session_id": existing_attempt.session_id,
                    },
                    server_secret,
                )
                return JoinRoomResult(
                    attempt=existing_attempt,
                    student=student,
                    exam=exam,
                    attempt_token=token,
                )

            # Conflict: another browser/device already holds an active binding
            record_audit_event(
                db,
                actor_type="student",
                actor_id=student.id,
                action="DUPLICATE_ATTEMPT_BLOCKED",
                target_type="attempt",
                target_id=existing_attempt.id,
                details={"exam_id": exam.id},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Học sinh này đã đăng nhập trên một thiết bị khác. "
                    "Vui lòng báo giáo viên xác minh và đặt lại thiết bị."
                ),
            )

        # Device binding was revoked by teacher -> allow clean rebind!
        new_session_id = str(uuid.uuid4())
        existing_attempt.session_id = new_session_id
        existing_attempt.last_seen = now
        db.add(
            DeviceBinding(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                attempt_id=existing_attempt.id,
                device_token_hash=browser_hash,
                user_agent_hint=user_agent[:180],
                bound_at=now,
            )
        )
        record_audit_event(
            db,
            actor_type="student",
            actor_id=student.id,
            action="DEVICE_REBOUND",
            target_type="attempt",
            target_id=existing_attempt.id,
            details={"exam_id": exam.id},
        )
        db.commit()
        token = sign_token(
            {
                "role": "student",
                "attempt_id": existing_attempt.id,
                "exam_id": exam.id,
                "student_id": student.id,
                "session_id": existing_attempt.session_id,
            },
            server_secret,
        )
        return JoinRoomResult(
            attempt=existing_attempt,
            student=student,
            exam=exam,
            attempt_token=token,
        )

    # First join: create single attempt atomically guarded by UniqueConstraint(exam_id, student_id)
    new_attempt = Attempt(
        id=str(uuid.uuid4()),
        exam_id=exam.id,
        student_id=student.id,
        session_id=str(uuid.uuid4()),
        state="PENDING_APPROVAL",
        last_seen=now,
        latest_revision=0,
    )
    db.add(new_attempt)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Yêu cầu tham gia bị trùng lặp đồng thời. Vui lòng thử lại hoặc báo giáo viên.",
        ) from exc

    db.add(
        DeviceBinding(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            attempt_id=new_attempt.id,
            device_token_hash=browser_hash,
            user_agent_hint=user_agent[:180],
            bound_at=now,
        )
    )
    if matched_invite.used_at is None:
        matched_invite.used_at = now
    db.commit()
    db.refresh(new_attempt)

    token = sign_token(
        {
            "role": "student",
            "attempt_id": new_attempt.id,
            "exam_id": exam.id,
            "student_id": student.id,
            "session_id": new_attempt.session_id,
        },
        server_secret,
    )
    return JoinRoomResult(
        attempt=new_attempt,
        student=student,
        exam=exam,
        attempt_token=token,
    )


def approve_attempt(db: Session, *, exam_id: str, attempt_id: str, teacher_id: int) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên học sinh.")
    if attempt.state == "PENDING_APPROVAL":
        attempt.state = "READY"
        record_audit_event(
            db,
            actor_type="teacher",
            actor_id=str(teacher_id),
            action="APPROVE_STUDENT_ATTEMPT",
            target_type="attempt",
            target_id=attempt.id,
            details={"exam_id": exam_id, "student_id": attempt.student_id},
        )
        db.commit()
        db.refresh(attempt)
    return attempt


def approve_all_pending(db: Session, *, exam_id: str, teacher_id: int) -> int:
    pending = (
        db.execute(
            select(Attempt).where(Attempt.exam_id == exam_id, Attempt.state == "PENDING_APPROVAL")
        )
        .scalars()
        .all()
    )
    for att in pending:
        att.state = "READY"
    if pending:
        record_audit_event(
            db,
            actor_type="teacher",
            actor_id=str(teacher_id),
            action="APPROVE_ALL_PENDING",
            target_type="exam",
            target_id=exam_id,
            details={"approved_count": len(pending)},
        )
        db.commit()
    return len(pending)


def reset_attempt_device(
    db: Session,
    *,
    exam_id: str,
    attempt_id: str,
    reason: str,
    teacher_id: int,
) -> Attempt:
    clean_reason = reason.strip()
    if len(clean_reason) < 3:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập lý do đặt lại thiết bị (tối thiểu 3 ký tự).",
        )
    attempt = db.get(Attempt, attempt_id)
    if attempt is None or attempt.exam_id != exam_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên học sinh.")

    now = datetime.now(UTC)
    active_bindings = (
        db.execute(
            select(DeviceBinding).where(
                DeviceBinding.attempt_id == attempt.id,
                DeviceBinding.revoked_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for binding in active_bindings:
        binding.revoked_at = now

    attempt.session_id = str(uuid.uuid4())
    attempt.presence_state = "OFFLINE"
    db.add(
        PresenceEvent(
            id=str(uuid.uuid4()),
            exam_id=exam_id,
            attempt_id=attempt.id,
            event_type="TEACHER_REBIND",
            server_time=now,
            details_json=json.dumps({"reason": clean_reason[:160]}, ensure_ascii=False),
        )
    )

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="TEACHER_RESET_DEVICE",
        target_type="attempt",
        target_id=attempt.id,
        details={
            "exam_id": exam_id,
            "student_id": attempt.student_id,
            "reason": clean_reason,
            "revoked_count": len(active_bindings),
        },
    )
    db.commit()
    db.refresh(attempt)
    return attempt
