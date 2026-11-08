"""Student exam paper delivery (zero key leak), commit-before-ACK idempotent answer writes, sync & submit."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db.locks import EXAM_WRITE_LOCK
from app.db.models import (
    AnswerRevision,
    Attempt,
    Exam,
    ExamQuestion,
    Incident,
    QuestionVersion,
    Submission,
)
from app.security.auth import StudentPrincipal
from app.services.audit_service import record_audit_event
from app.services.exam_service import (
    compute_remaining_seconds,
    ensure_aware,
    ensure_student_permutation,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

OPTION_LETTERS = "ABCDEFGHIJ"


@dataclass(frozen=True)
class AnswerAckResult:
    attempt_id: str
    question_version_id: str
    selected_option_ids: list[str]
    server_revision: int
    idempotency_key: str
    committed_at: datetime
    duplicate: bool


@dataclass(frozen=True)
class SubmitAttemptResult:
    submission: Submission
    already_submitted: bool


def _validate_student_attempt_ownership(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
) -> tuple[Attempt, Exam]:
    if attempt_id != student.attempt_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập bài làm của học sinh khác.",
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
        raise HTTPException(status_code=404, detail="Kỳ thi không tồn tại.")
    return attempt, exam


def _latest_answers_map(db: Session, attempt_id: str) -> dict[str, dict[str, Any]]:
    revs = (
        db.execute(
            select(AnswerRevision)
            .where(AnswerRevision.attempt_id == attempt_id)
            .order_by(AnswerRevision.revision.asc(), AnswerRevision.committed_at.asc())
        )
        .scalars()
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for r in revs:
        out[r.question_version_id] = {
            "selected_option_ids": list(json.loads(r.selected_option_ids_json)),
            "server_revision": r.revision,
            "committed_at": r.committed_at.isoformat(),
        }
    return out


def get_student_paper_payload(db: Session, *, student: StudentPrincipal) -> dict[str, Any]:
    """Return personalized shuffled exam paper NEVER containing answer_key_versions."""
    attempt, exam = _validate_student_attempt_ownership(
        db,
        attempt_id=student.attempt_id,
        student=student,
    )
    if attempt.state == "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Giáo viên chưa duyệt học sinh vào phòng thi.",
        )
    if exam.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phòng thi chưa mở đề hoặc đã đóng.",
        )
    if attempt.state in {"LOCKED_PENDING_REVIEW", "ENDED_WITH_REVIEW"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bài thi đang tạm khóa chờ giáo viên xác minh.",
        )
    if attempt.state == "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã nộp bài thi này.",
        )

    now = datetime.now(UTC)
    if attempt.state == "READY":
        attempt.state = "ACTIVE"
        attempt.presence_state = "ACTIVE"
        attempt.last_heartbeat_at = now
        attempt.last_seen = now
        if attempt.started_at is None:
            attempt.started_at = now
        db.commit()
        db.refresh(attempt)
    elif attempt.state == "ACTIVE" and attempt.last_heartbeat_at is None:
        attempt.presence_state = "ACTIVE"
        attempt.last_heartbeat_at = now
        attempt.last_seen = now
        db.commit()

    perm = ensure_student_permutation(db, exam=exam, student_id=student.student_id)
    db.commit()

    q_order: list[str] = json.loads(perm.question_order_json)
    opt_order_map: dict[str, list[str]] = json.loads(perm.option_order_json)

    versions = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(q_order)))
        .scalars()
        .all()
    }

    questions_payload: list[dict[str, Any]] = []
    for display_idx, qvid in enumerate(q_order, start=1):
        qv = versions[qvid]
        blocks = json.loads(qv.content_blocks_json)
        raw_options = json.loads(qv.options_json)
        opt_by_id = {str(o["option_id"]): o for o in raw_options}
        ordered_opt_ids = opt_order_map.get(qvid, list(opt_by_id.keys()))

        display_options = []
        for o_idx, oid in enumerate(ordered_opt_ids):
            if oid not in opt_by_id:
                continue
            label = OPTION_LETTERS[o_idx] if o_idx < len(OPTION_LETTERS) else str(o_idx + 1)
            display_options.append(
                {
                    "option_id": oid,
                    "display_label": label,
                    "blocks": opt_by_id[oid]["blocks"],
                }
            )

        questions_payload.append(
            {
                "position": display_idx,
                "question_version_id": qvid,
                "blocks": blocks,
                "options": display_options,
            }
        )

    heartbeat_s = 3
    try:
        raw_pol = json.loads(exam.policy_json or "{}")
        if isinstance(raw_pol, dict) and isinstance(raw_pol.get("heartbeat_s"), int | float):
            heartbeat_s = max(1, int(raw_pol["heartbeat_s"]))
    except Exception:
        heartbeat_s = 3

    return {
        "attempt_id": attempt.id,
        "exam_id": exam.id,
        "exam_title": exam.title,
        "room_code": exam.room_code,
        "exam_status": exam.status,
        "attempt_state": attempt.state,
        "presence_state": attempt.presence_state,
        "extra_time_s": attempt.extra_time_s,
        "heartbeat_s": heartbeat_s,
        "is_paused": exam.paused_at is not None,
        "remaining_s": compute_remaining_seconds(exam, attempt, now),
        "server_time_utc": now.isoformat(),
        "deadline_at": exam.deadline_at.isoformat() if exam.deadline_at else None,
        "latest_revision": attempt.latest_revision,
        "questions": questions_payload,
        "saved_answers": _latest_answers_map(db, attempt.id),
    }


def save_answer_revision(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
    question_version_id: str,
    selected_option_ids: list[str],
    idempotency_key: str,
    client_timestamp: str | None,
) -> AnswerAckResult:
    """Commit answer revision inside SQLite transaction BEFORE returning ACK."""
    attempt, exam = _validate_student_attempt_ownership(db, attempt_id=attempt_id, student=student)

    # Check existing idempotent commit first (safe replay!)
    existing = db.execute(
        select(AnswerRevision).where(
            AnswerRevision.attempt_id == attempt.id,
            AnswerRevision.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return AnswerAckResult(
            attempt_id=attempt.id,
            question_version_id=existing.question_version_id,
            selected_option_ids=list(json.loads(existing.selected_option_ids_json)),
            server_revision=existing.revision,
            idempotency_key=existing.idempotency_key,
            committed_at=existing.committed_at,
            duplicate=True,
        )

    if attempt.state == "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bài làm đã được nộp, không thể thay đổi đáp án.",
        )
    if attempt.state not in {"READY", "ACTIVE"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phiên làm bài hiện chưa được kích hoạt hoặc đang tạm khóa.",
        )
    if exam.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng thi đã đóng hoặc chưa bắt đầu.",
        )
    if exam.paused_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phòng thi đang tạm dừng bởi giáo viên.",
        )

    # Authoritative server deadline verification (ignore client clock tamper!)
    now = datetime.now(UTC)
    if exam.deadline_at is not None:
        effective_deadline = (
            ensure_aware(exam.deadline_at)
            + timedelta(seconds=attempt.extra_time_s)
            + timedelta(seconds=5)  # bounded in-flight network tolerance
        )
        if now > effective_deadline:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Đã hết thời gian làm bài theo đồng hồ máy chủ.",
            )

    # Validate question belongs to exam and options belong to question
    eq = db.execute(
        select(ExamQuestion).where(
            ExamQuestion.exam_id == exam.id,
            ExamQuestion.question_version_id == question_version_id,
        )
    ).scalar_one_or_none()
    if eq is None:
        raise HTTPException(status_code=400, detail="Câu hỏi không thuộc đề thi này.")

    qv = db.get(QuestionVersion, question_version_id)
    if qv is None:
        raise HTTPException(status_code=400, detail="Không tìm thấy phiên bản câu hỏi.")
    valid_option_ids = {str(o["option_id"]) for o in json.loads(qv.options_json)}
    clean_selected = list(dict.fromkeys(str(oid) for oid in selected_option_ids))
    if any(oid not in valid_option_ids for oid in clean_selected):
        raise HTTPException(status_code=400, detail="Phương án lựa chọn không hợp lệ cho câu hỏi này.")

    with EXAM_WRITE_LOCK:
        # Refresh inside lock to read latest committed revision safely under concurrency
        db.expire_all()
        attempt_locked = db.get(Attempt, attempt.id)
        if attempt_locked is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi.")
        if attempt_locked.state in {"LOCKED_PENDING_REVIEW", "ENDED_WITH_REVIEW"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Phiên làm bài đang tạm khóa chờ giáo viên xác minh.",
            )
        if attempt_locked.state == "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bài làm đã được nộp, không thể thay đổi đáp án.",
            )

        existing_locked = db.execute(
            select(AnswerRevision).where(
                AnswerRevision.attempt_id == attempt.id,
                AnswerRevision.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_locked is not None:
            return AnswerAckResult(
                attempt_id=attempt.id,
                question_version_id=existing_locked.question_version_id,
                selected_option_ids=list(json.loads(existing_locked.selected_option_ids_json)),
                server_revision=existing_locked.revision,
                idempotency_key=existing_locked.idempotency_key,
                committed_at=existing_locked.committed_at,
                duplicate=True,
            )

        if attempt_locked.state == "READY":
            attempt_locked.state = "ACTIVE"
            attempt_locked.presence_state = "ACTIVE"
            if attempt_locked.started_at is None:
                attempt_locked.started_at = now
        attempt_locked.last_heartbeat_at = now
        if attempt_locked.presence_state != "ACTIVE":
            attempt_locked.presence_state = "ACTIVE"

        next_revision = attempt_locked.latest_revision + 1
        attempt_locked.latest_revision = next_revision
        attempt_locked.last_seen = now

        rev = AnswerRevision(
            id=str(uuid.uuid4()),
            attempt_id=attempt_locked.id,
            question_version_id=question_version_id,
            selected_option_ids_json=json.dumps(clean_selected),
            revision=next_revision,
            idempotency_key=idempotency_key,
            client_timestamp=client_timestamp[:64] if client_timestamp else None,
            committed_at=now,
        )
        db.add(rev)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            replay = db.execute(
                select(AnswerRevision).where(
                    AnswerRevision.attempt_id == attempt.id,
                    AnswerRevision.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if replay is not None:
                return AnswerAckResult(
                    attempt_id=attempt.id,
                    question_version_id=replay.question_version_id,
                    selected_option_ids=list(json.loads(replay.selected_option_ids_json)),
                    server_revision=replay.revision,
                    idempotency_key=replay.idempotency_key,
                    committed_at=replay.committed_at,
                    duplicate=True,
                )
            raise

    db.refresh(rev)
    return AnswerAckResult(
        attempt_id=attempt.id,
        question_version_id=rev.question_version_id,
        selected_option_ids=clean_selected,
        server_revision=rev.revision,
        idempotency_key=rev.idempotency_key,
        committed_at=rev.committed_at,
        duplicate=False,
    )


def get_canonical_sync_state(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
) -> dict[str, Any]:
    attempt, exam = _validate_student_attempt_ownership(db, attempt_id=attempt_id, student=student)
    now = datetime.now(UTC)
    submission = db.execute(
        select(Submission).where(Submission.attempt_id == attempt.id)
    ).scalar_one_or_none()
    open_incident = db.execute(
        select(Incident)
        .where(Incident.attempt_id == attempt.id, Incident.state == "OPEN")
        .order_by(Incident.opened_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return {
        "attempt_id": attempt.id,
        "exam_id": exam.id,
        "exam_status": exam.status,
        "attempt_state": attempt.state,
        "presence_state": attempt.presence_state,
        "extra_time_s": attempt.extra_time_s,
        "is_paused": exam.paused_at is not None,
        "remaining_s": compute_remaining_seconds(exam, attempt, now),
        "server_time_utc": now.isoformat(),
        "latest_revision": attempt.latest_revision,
        "saved_answers": _latest_answers_map(db, attempt.id),
        "submitted_at": submission.submitted_at.isoformat() if submission else None,
        "snapshot_hash": submission.snapshot_hash if submission else None,
        "incident_reason": open_incident.summary if open_incident else None,
    }


def submit_student_attempt(
    db: Session,
    *,
    attempt_id: str,
    student: StudentPrincipal,
) -> SubmitAttemptResult:
    attempt, exam = _validate_student_attempt_ownership(db, attempt_id=attempt_id, student=student)
    if attempt.state == "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Học sinh chưa được duyệt vào phòng thi.",
        )

    existing = db.execute(
        select(Submission).where(Submission.attempt_id == attempt.id)
    ).scalar_one_or_none()
    if existing is not None:
        return SubmitAttemptResult(submission=existing, already_submitted=True)

    if exam.status not in {"RUNNING", "CLOSED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể nộp bài khi phòng thi chưa bắt đầu.",
        )
    if attempt.state in {"LOCKED_PENDING_REVIEW", "ENDED_WITH_REVIEW"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bài thi đang tạm khóa chờ giáo viên xử lý.",
        )

    with EXAM_WRITE_LOCK:
        db.expire_all()
        existing_locked = db.execute(
            select(Submission).where(Submission.attempt_id == attempt.id)
        ).scalar_one_or_none()
        if existing_locked is not None:
            return SubmitAttemptResult(submission=existing_locked, already_submitted=True)

        attempt_locked = db.get(Attempt, attempt.id)
        if attempt_locked is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi.")
        if attempt_locked.state in {"LOCKED_PENDING_REVIEW", "ENDED_WITH_REVIEW"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bài thi đang tạm khóa chờ giáo viên xử lý.",
            )

        revs = (
            db.execute(
                select(AnswerRevision)
                .where(AnswerRevision.attempt_id == attempt.id)
                .order_by(AnswerRevision.revision.asc(), AnswerRevision.committed_at.asc())
            )
            .scalars()
            .all()
        )
        answers_snapshot: dict[str, list[str]] = {}
        for r in revs:
            answers_snapshot[r.question_version_id] = list(json.loads(r.selected_option_ids_json))

        canon_json = json.dumps(answers_snapshot, sort_keys=True, ensure_ascii=False)
        snap_hash = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)

        submission = Submission(
            id=str(uuid.uuid4()),
            attempt_id=attempt.id,
            exam_id=exam.id,
            student_id=attempt.student_id,
            answer_snapshot_json=canon_json,
            snapshot_hash=snap_hash,
            submission_mode="student_submit",
            submitted_at=now,
        )
        try:
            db.add(submission)
            db.flush()
            attempt_locked.state = "SUBMITTED"
            attempt_locked.submitted_at = now
            attempt_locked.last_seen = now

            record_audit_event(
                db,
                actor_type="student",
                actor_id=student.student_id,
                action="SUBMIT_ATTEMPT",
                target_type="attempt",
                target_id=attempt.id,
                details={
                    "exam_id": exam.id,
                    "answered_questions": len(answers_snapshot),
                    "snapshot_hash": snap_hash,
                },
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            replay = db.execute(
                select(Submission).where(Submission.attempt_id == attempt.id)
            ).scalar_one()
            return SubmitAttemptResult(submission=replay, already_submitted=True)

    db.refresh(submission)
    return SubmitAttemptResult(submission=submission, already_submitted=False)
