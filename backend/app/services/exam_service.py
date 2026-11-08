"""Exam lifecycle state machine, deterministic seeded permutation, server timer, and close handling."""

from __future__ import annotations

import hashlib
import json
import math
import random
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.db.models import (
    AnswerKeyVersion,
    AnswerRevision,
    Attempt,
    ClassMembership,
    Classroom,
    Exam,
    ExamPermutation,
    ExamQuestion,
    QuestionVersion,
    Student,
    StudentInvite,
    Submission,
)
from app.security.auth import INVITE_ALPHABET, generate_invite_code, hash_secret_value
from app.services.audit_service import record_audit_event
from app.services.room_service import IssuedInviteDTO
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

ALLOWED_EXAM_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"READY", "WAITING", "CANCELLED"},
    "READY": {"WAITING", "CANCELLED"},
    "WAITING": {"RUNNING", "CANCELLED"},
    "RUNNING": {"CLOSED", "CANCELLED"},
    "CLOSED": {"REVIEWED"},
    "REVIEWED": {"PUBLISHED"},
    "PUBLISHED": {"ARCHIVED"},
    "ARCHIVED": set(),
    "CANCELLED": set(),
}


def ensure_aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def validate_exam_transition(current_status: str, target_status: str) -> None:
    allowed = ALLOWED_EXAM_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Không thể chuyển trạng thái kỳ thi từ {current_status} sang {target_status}.",
        )


def compute_remaining_seconds(exam: Exam, attempt: Attempt | None = None, now: datetime | None = None) -> int:
    """Compute authoritative server-side remaining seconds (never trusts client clock)."""
    if exam.status in {"DRAFT", "READY", "WAITING"}:
        extra = attempt.extra_time_s if attempt else 0
        return max(0, exam.duration_s + extra)
    if exam.status != "RUNNING" or exam.deadline_at is None:
        return 0
    ref = ensure_aware(exam.paused_at) if exam.paused_at is not None else (now or datetime.now(UTC))
    extra = attempt.extra_time_s if attempt else 0
    deadline = ensure_aware(exam.deadline_at) + timedelta(seconds=extra)
    return max(0, math.ceil((deadline - ref).total_seconds()))


def _generate_unique_room_code(db: Session) -> str:
    code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))
    while db.execute(select(Exam).where(Exam.room_code == code)).scalar_one_or_none() is not None:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))
    return code


def create_configured_exam(
    db: Session,
    *,
    classroom_id: str,
    title: str,
    duration_s: int,
    question_version_ids: list[str],
    shuffle_questions: bool,
    shuffle_options: bool,
    seed: int | None,
    policy: dict[str, int] | None,
    teacher_id: int,
    open_waiting: bool = False,
    invite_ttl_minutes: int = 120,
    server_secret: bytes = b"",
) -> tuple[Exam, list[IssuedInviteDTO]]:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None or classroom.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")

    clean_qids = list(dict.fromkeys(qid.strip() for qid in question_version_ids if qid.strip()))
    if not clean_qids:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng chọn ít nhất 1 câu hỏi đã duyệt từ ngân hàng đề.",
        )

    # Verify every QuestionVersion exists and has an approved AnswerKeyVersion
    versions = (
        db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(clean_qids))).scalars().all()
    )
    version_map = {v.id: v for v in versions}
    missing = [qid for qid in clean_qids if qid not in version_map]
    if missing:
        raise HTTPException(status_code=400, detail="Một số câu hỏi không tồn tại trong ngân hàng đề.")

    keyed_qids = set(
        db.execute(
            select(AnswerKeyVersion.question_version_id).where(
                AnswerKeyVersion.question_version_id.in_(clean_qids)
            )
        )
        .scalars()
        .all()
    )
    unkeyed = [qid for qid in clean_qids if qid not in keyed_qids]
    if unkeyed:
        raise HTTPException(
            status_code=400,
            detail="Có câu hỏi chưa được xác nhận đáp án đúng; không thể đưa vào đề thi.",
        )

    final_seed = seed if (seed is not None and seed > 0) else secrets.randbelow(2_147_483_647) + 1
    default_policy: dict[str, int] = {
        "heartbeat_s": 3,
        "suspected_s": 5,
        "disconnect_s": 15,
        "lock_after_s": 30,
        "grace_submit_s": 30,
    }
    if policy:
        default_policy.update({k: int(v) for k, v in policy.items()})
    exam = Exam(
        id=str(uuid.uuid4()),
        classroom_id=classroom_id,
        room_code=_generate_unique_room_code(db),
        title=title.strip() or f"Kiểm tra {classroom.name}",
        duration_s=max(60, duration_s),
        status="READY",
        seed=final_seed,
        shuffle_questions=shuffle_questions,
        shuffle_options=shuffle_options,
        policy_json=json.dumps(default_policy),
    )
    db.add(exam)
    db.flush()

    for idx, qvid in enumerate(clean_qids, start=1):
        db.add(
            ExamQuestion(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                question_version_id=qvid,
                position=idx,
                weight=1.0,
            )
        )

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="CONFIGURE_EXAM",
        target_type="exam",
        target_id=exam.id,
        details={
            "classroom_id": classroom_id,
            "question_count": len(clean_qids),
            "duration_s": exam.duration_s,
            "shuffle_questions": shuffle_questions,
            "shuffle_options": shuffle_options,
        },
    )

    issued: list[IssuedInviteDTO] = []
    if open_waiting:
        if not server_secret:
            raise HTTPException(status_code=500, detail="Thiếu khóa ký mã mời cục bộ.")
        issued = _transition_to_waiting_and_issue_invites(
            db,
            exam=exam,
            invite_ttl_minutes=invite_ttl_minutes,
            teacher_id=teacher_id,
            server_secret=server_secret,
        )

    db.commit()
    db.refresh(exam)
    return exam, issued


def attach_questions_to_exam(
    db: Session,
    *,
    exam_id: str,
    question_version_ids: list[str],
    teacher_id: int,
) -> int:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    if exam.status not in {"DRAFT", "READY", "WAITING"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể thay đổi danh sách câu hỏi khi kỳ thi đã bắt đầu.",
        )
    clean_qids = list(dict.fromkeys(qid.strip() for qid in question_version_ids if qid.strip()))
    if not clean_qids:
        raise HTTPException(status_code=400, detail="Cần chọn ít nhất 1 câu hỏi.")

    existing = (
        db.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)).scalars().all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    for idx, qvid in enumerate(clean_qids, start=1):
        qv = db.get(QuestionVersion, qvid)
        if qv is None:
            raise HTTPException(status_code=400, detail=f"Không tìm thấy câu hỏi {qvid}.")
        db.add(
            ExamQuestion(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                question_version_id=qvid,
                position=idx,
                weight=1.0,
            )
        )

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="SET_EXAM_QUESTIONS",
        target_type="exam",
        target_id=exam.id,
        details={"question_count": len(clean_qids)},
    )
    db.commit()
    return len(clean_qids)


def _transition_to_waiting_and_issue_invites(
    db: Session,
    *,
    exam: Exam,
    invite_ttl_minutes: int,
    teacher_id: int,
    server_secret: bytes,
) -> list[IssuedInviteDTO]:
    validate_exam_transition(exam.status, "WAITING")
    exam.status = "WAITING"

    students = (
        db.execute(
            select(Student)
            .join(ClassMembership, ClassMembership.student_id == Student.id)
            .where(
                ClassMembership.classroom_id == exam.classroom_id,
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
        details={"room_code": exam.room_code, "student_count": len(issued)},
    )
    return issued


def open_exam_waiting_room(
    db: Session,
    *,
    exam_id: str,
    invite_ttl_minutes: int,
    teacher_id: int,
    server_secret: bytes,
) -> tuple[Exam, list[IssuedInviteDTO]]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    issued = _transition_to_waiting_and_issue_invites(
        db,
        exam=exam,
        invite_ttl_minutes=invite_ttl_minutes,
        teacher_id=teacher_id,
        server_secret=server_secret,
    )
    db.commit()
    db.refresh(exam)
    return exam, issued


def ensure_student_permutation(db: Session, *, exam: Exam, student_id: str) -> ExamPermutation:
    """Return existing frozen permutation or deterministically generate & freeze it."""
    existing = db.execute(
        select(ExamPermutation).where(
            ExamPermutation.exam_id == exam.id,
            ExamPermutation.student_id == student_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    exam_questions = (
        db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.position.asc())
        )
        .scalars()
        .all()
    )
    if not exam_questions:
        raise HTTPException(status_code=400, detail="Kỳ thi chưa có câu hỏi nào.")

    qids = [eq.question_version_id for eq in exam_questions]
    versions = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(qids)))
        .scalars()
        .all()
    }

    digest = hashlib.sha256(f"{exam.seed}:{exam.id}:{student_id}".encode()).digest()
    student_seed = int.from_bytes(digest[:8], "big")
    rng = random.Random(student_seed)

    q_order = list(qids)
    if exam.shuffle_questions and len(q_order) > 1:
        rng.shuffle(q_order)

    option_order: dict[str, list[str]] = {}
    for qvid in q_order:
        qv = versions[qvid]
        opts = json.loads(qv.options_json)
        opt_ids = [str(opt["option_id"]) for opt in opts]
        if exam.shuffle_options and len(opt_ids) > 1:
            rng.shuffle(opt_ids)
        option_order[qvid] = opt_ids

    perm = ExamPermutation(
        id=str(uuid.uuid4()),
        exam_id=exam.id,
        student_id=student_id,
        seed=student_seed & 0x7FFFFFFF,
        question_order_json=json.dumps(q_order),
        option_order_json=json.dumps(option_order),
    )
    db.add(perm)
    try:
        db.flush()
        return perm
    except IntegrityError:
        db.rollback()
        existing_after = db.execute(
            select(ExamPermutation).where(
                ExamPermutation.exam_id == exam.id,
                ExamPermutation.student_id == student_id,
            )
        ).scalar_one()
        return existing_after


def start_exam_session(db: Session, *, exam_id: str, teacher_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    validate_exam_transition(exam.status, "RUNNING")

    eqs = (
        db.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id))
        .scalars()
        .all()
    )
    if not eqs:
        raise HTTPException(
            status_code=400,
            detail="Kỳ thi chưa có câu hỏi nào. Vui lòng gắn câu hỏi từ ngân hàng đề trước khi bắt đầu.",
        )

    now = datetime.now(UTC)
    exam.status = "RUNNING"
    exam.start_at = now
    exam.deadline_at = now + timedelta(seconds=exam.duration_s)
    exam.paused_at = None

    # Pre-freeze deterministic permutations for active students in classroom
    students = (
        db.execute(
            select(Student.id)
            .join(ClassMembership, ClassMembership.student_id == Student.id)
            .where(
                ClassMembership.classroom_id == exam.classroom_id,
                ClassMembership.active_to.is_(None),
                Student.archived_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for st_id in students:
        ensure_student_permutation(db, exam=exam, student_id=st_id)

    # Transition approved READY attempts -> ACTIVE
    ready_attempts = (
        db.execute(select(Attempt).where(Attempt.exam_id == exam.id, Attempt.state == "READY"))
        .scalars()
        .all()
    )
    for att in ready_attempts:
        att.state = "ACTIVE"
        att.presence_state = "ACTIVE"
        att.started_at = now
        att.last_heartbeat_at = now
        att.last_seen = now

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="START_EXAM",
        target_type="exam",
        target_id=exam.id,
        details={
            "duration_s": exam.duration_s,
            "activated_attempts": len(ready_attempts),
            "deadline_at": exam.deadline_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(exam)
    return exam


def pause_exam_session(db: Session, *, exam_id: str, reason: str, teacher_id: int) -> Exam:
    clean_reason = reason.strip()
    if len(clean_reason) < 3:
        raise HTTPException(status_code=400, detail="Vui lòng nhập lý do tạm dừng (>= 3 ký tự).")
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    if exam.status != "RUNNING":
        raise HTTPException(status_code=409, detail="Chỉ có thể tạm dừng khi phòng thi đang diễn ra.")
    if exam.paused_at is not None:
        raise HTTPException(status_code=409, detail="Phòng thi đã ở trạng thái tạm dừng.")

    now = datetime.now(UTC)
    exam.paused_at = now
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="PAUSE_EXAM",
        target_type="exam",
        target_id=exam.id,
        details={"reason": clean_reason, "paused_at": now.isoformat()},
    )
    db.commit()
    db.refresh(exam)
    return exam


def resume_exam_session(db: Session, *, exam_id: str, teacher_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    if exam.status != "RUNNING" or exam.paused_at is None or exam.deadline_at is None:
        raise HTTPException(status_code=409, detail="Phòng thi hiện không ở trạng thái tạm dừng.")

    now = datetime.now(UTC)
    delta_s = max(0, math.ceil((now - ensure_aware(exam.paused_at)).total_seconds()))
    exam.paused_total_s += delta_s
    exam.deadline_at = ensure_aware(exam.deadline_at) + timedelta(seconds=delta_s)
    exam.paused_at = None

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="RESUME_EXAM",
        target_type="exam",
        target_id=exam.id,
        details={"paused_delta_s": delta_s, "new_deadline_at": exam.deadline_at.isoformat()},
    )
    db.commit()
    db.refresh(exam)
    return exam


def _build_canonical_answers_for_attempt(db: Session, attempt_id: str) -> dict[str, list[str]]:
    revs = (
        db.execute(
            select(AnswerRevision)
            .where(AnswerRevision.attempt_id == attempt_id)
            .order_by(AnswerRevision.revision.asc(), AnswerRevision.committed_at.asc())
        )
        .scalars()
        .all()
    )
    snapshot: dict[str, list[str]] = {}
    for rev in revs:
        snapshot[rev.question_version_id] = list(json.loads(rev.selected_option_ids_json))
    return snapshot


def close_exam_session(db: Session, *, exam_id: str, reason: str, teacher_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    validate_exam_transition(exam.status, "CLOSED")

    now = datetime.now(UTC)
    if exam.paused_at is not None and exam.deadline_at is not None:
        delta_s = max(0, math.ceil((now - ensure_aware(exam.paused_at)).total_seconds()))
        exam.paused_total_s += delta_s
        exam.paused_at = None

    exam.status = "CLOSED"
    exam.closed_at = now

    # Auto-snapshot all non-submitted attempts so evidence is frozen cleanly
    attempts = db.execute(select(Attempt).where(Attempt.exam_id == exam.id)).scalars().all()
    existing_sub_attempts = set(
        db.execute(select(Submission.attempt_id).where(Submission.exam_id == exam.id))
        .scalars()
        .all()
    )
    auto_finalized = 0
    active_states = {
        "PENDING_APPROVAL",
        "READY",
        "ACTIVE",
        "SUSPECTED",
        "DISCONNECTED",
        "LOCKED_PENDING_REVIEW",
    }
    for att in attempts:
        if att.id in existing_sub_attempts:
            continue
        if att.state in active_states:
            answers = _build_canonical_answers_for_attempt(db, att.id)
            canon_json = json.dumps(answers, sort_keys=True, ensure_ascii=False)
            snap_hash = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()
            db.add(
                Submission(
                    id=str(uuid.uuid4()),
                    attempt_id=att.id,
                    exam_id=exam.id,
                    student_id=att.student_id,
                    answer_snapshot_json=canon_json,
                    snapshot_hash=snap_hash,
                    submission_mode="teacher_close_auto",
                    submitted_at=now,
                )
            )
            att.state = "SUBMITTED"
            att.submitted_at = now
            auto_finalized += 1

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="CLOSE_EXAM",
        target_type="exam",
        target_id=exam.id,
        details={"reason": reason.strip() or "Đóng phòng thu bài", "auto_finalized": auto_finalized},
    )
    db.commit()
    db.refresh(exam)
    return exam
