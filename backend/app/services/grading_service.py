"""Pure scoring engine, key/score/receipt versioning, publication gate, and Phúc khảo trace."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from app.core.config import Settings
from app.db.locks import EXAM_WRITE_LOCK
from app.db.models import (
    AnswerKeyVersion,
    AnswerRevision,
    Attempt,
    AuditEvent,
    ClassMembership,
    Classroom,
    Exam,
    ExamPermutation,
    ExamQuestion,
    GradeRun,
    Incident,
    PresenceEvent,
    QuestionVersion,
    ReceiptVersion,
    ScoreVersion,
    Student,
    Submission,
)
from app.security.auth import StudentPrincipal
from app.services.audit_service import record_audit_event
from app.services.export_service import (
    compute_exam_statistics,
    generate_and_save_receipt_version,
    sanitize_download_filename,
)
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

OPTION_LETTERS = "ABCDEFGHIJ"


@dataclass(frozen=True)
class QuestionScoringSpec:
    question_version_id: str
    position: int
    weight: float
    correct_option_ids: tuple[str, ...]
    key_version_id: str = ""
    key_version_number: int = 1


@dataclass(frozen=True)
class QuestionBreakdownItem:
    question_version_id: str
    position: int
    weight: float
    selected_option_ids: list[str]
    correct_option_ids: list[str]
    is_correct: bool
    earned_points: float


@dataclass(frozen=True)
class ScoringOutcome:
    raw_correct: int
    total_questions: int
    max_points: float
    earned_points: float
    score_10: float
    breakdown: list[QuestionBreakdownItem]


def score_submission_answers(
    answer_snapshot: dict[str, list[str]],
    specs: list[QuestionScoringSpec],
) -> ScoringOutcome:
    """Pure, deterministic, side-effect-free scoring function over canonical Submission snapshots."""
    raw_correct = 0
    max_points = 0.0
    earned_points = 0.0
    breakdown: list[QuestionBreakdownItem] = []

    ordered_specs = sorted(specs, key=lambda s: s.position)
    for spec in ordered_specs:
        raw_selected = answer_snapshot.get(spec.question_version_id, [])
        clean_selected = list(dict.fromkeys(str(oid) for oid in raw_selected if str(oid)))
        clean_correct = list(dict.fromkeys(str(oid) for oid in spec.correct_option_ids if str(oid)))

        is_correct = bool(clean_correct) and set(clean_selected) == set(clean_correct)
        item_earned = round(spec.weight, 4) if is_correct else 0.0
        max_points += spec.weight
        earned_points += item_earned
        if is_correct:
            raw_correct += 1

        breakdown.append(
            QuestionBreakdownItem(
                question_version_id=spec.question_version_id,
                position=spec.position,
                weight=round(spec.weight, 4),
                selected_option_ids=clean_selected,
                correct_option_ids=clean_correct,
                is_correct=is_correct,
                earned_points=item_earned,
            )
        )

    score_10 = round((earned_points / max_points) * 10.0, 2) if max_points > 0 else 0.0
    return ScoringOutcome(
        raw_correct=raw_correct,
        total_questions=len(ordered_specs),
        max_points=round(max_points, 4),
        earned_points=round(earned_points, 4),
        score_10=score_10,
        breakdown=breakdown,
    )


def _hash_canonical(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _latest_key_version_for_qvid(db: Session, question_version_id: str) -> AnswerKeyVersion | None:
    return db.execute(
        select(AnswerKeyVersion)
        .where(AnswerKeyVersion.question_version_id == question_version_id)
        .order_by(AnswerKeyVersion.version_number.desc(), AnswerKeyVersion.approved_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _build_scoring_specs_for_exam(db: Session, exam_id: str) -> list[QuestionScoringSpec]:
    exam_qs = (
        db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.position.asc())
        )
        .scalars()
        .all()
    )
    if not exam_qs:
        raise HTTPException(status_code=400, detail="Kỳ thi chưa có câu hỏi nào để chấm điểm.")

    specs: list[QuestionScoringSpec] = []
    for eq in exam_qs:
        kv = _latest_key_version_for_qvid(db, eq.question_version_id)
        if kv is None:
            raise HTTPException(
                status_code=400,
                detail=f"Câu hỏi {eq.position} chưa có phiên bản đáp án chuẩn.",
            )
        correct_ids = tuple(str(x) for x in json.loads(kv.correct_option_ids_json))
        specs.append(
            QuestionScoringSpec(
                question_version_id=eq.question_version_id,
                position=eq.position,
                weight=float(eq.weight),
                correct_option_ids=correct_ids,
                key_version_id=kv.id,
                key_version_number=kv.version_number,
            )
        )
    return specs


def _execute_grade_run_locked(
    db: Session,
    *,
    exam: Exam,
    teacher_id: int,
    reason: str,
    updated_keys: dict[str, list[str]] | None = None,
    settings: Settings | None = None,
) -> tuple[GradeRun, int, int]:
    """Run grading or regrade inside EXAM_WRITE_LOCK; returns (GradeRun, scored_count, receipts_updated)."""
    clean_reason = reason.strip() or "Chấm điểm tự động"
    now = datetime.now(UTC)

    exam_qs = (
        db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.position.asc())
        )
        .scalars()
        .all()
    )
    exam_qvids = {eq.question_version_id for eq in exam_qs}

    max_run = int(
        db.execute(select(func.coalesce(func.max(GradeRun.run_number), 0)).where(GradeRun.exam_id == exam.id))
        .scalar_one()
    )
    next_run_number = max_run + 1

    if updated_keys:
        if len(reason.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Bắt buộc nhập lý do sửa đáp án (>= 3 ký tự).",
            )
        for qvid, raw_opts in updated_keys.items():
            if qvid not in exam_qvids:
                raise HTTPException(status_code=400, detail=f"Câu hỏi {qvid} không thuộc kỳ thi này.")
            qv = db.get(QuestionVersion, qvid)
            if qv is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy phiên bản câu hỏi.")
            valid_opt_ids = {str(o["option_id"]) for o in json.loads(qv.options_json)}
            clean_opts = list(dict.fromkeys(str(oid) for oid in raw_opts if str(oid)))
            if not clean_opts or any(oid not in valid_opt_ids for oid in clean_opts):
                raise HTTPException(
                    status_code=400,
                    detail="Danh sách đáp án đúng mới không hợp lệ hoặc đang để trống.",
                )

            prev_kv = _latest_key_version_for_qvid(db, qvid)
            prev_ids = list(json.loads(prev_kv.correct_option_ids_json)) if prev_kv else []
            if set(clean_opts) != set(prev_ids):
                new_ver_num = (prev_kv.version_number + 1) if prev_kv else 1
                new_kv = AnswerKeyVersion(
                    id=str(uuid.uuid4()),
                    question_version_id=qvid,
                    version_number=new_ver_num,
                    correct_option_ids_json=json.dumps(clean_opts),
                    reason=clean_reason[:300],
                    approved_by=teacher_id,
                    approved_at=now,
                )
                db.add(new_kv)
                db.flush()
                record_audit_event(
                    db,
                    actor_type="teacher",
                    actor_id=str(teacher_id),
                    action="UPDATE_ANSWER_KEY",
                    target_type="question_version",
                    target_id=qvid,
                    before_hash=_hash_canonical(prev_ids),
                    after_hash=_hash_canonical(clean_opts),
                    details={
                        "exam_id": exam.id,
                        "key_version_id": new_kv.id,
                        "version_number": new_ver_num,
                        "reason": clean_reason[:300],
                    },
                )

    if next_run_number > 1 and len(reason.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Bắt buộc nhập lý do chấm lại (>= 3 ký tự).",
        )

    specs = _build_scoring_specs_for_exam(db, exam.id)
    key_snapshot = {
        s.question_version_id: {
            "key_version_id": s.key_version_id,
            "key_version_number": s.key_version_number,
            "correct_option_ids": list(s.correct_option_ids),
            "weight": s.weight,
        }
        for s in specs
    }
    rubric_snapshot = {
        "scale": 10.0,
        "mode": "exact_match",
        "weights": {s.question_version_id: s.weight for s in specs},
    }

    grade_run = GradeRun(
        id=str(uuid.uuid4()),
        exam_id=exam.id,
        run_number=next_run_number,
        code_version="scoring-v1.0",
        rubric_version_json=json.dumps(rubric_snapshot, ensure_ascii=False),
        key_snapshot_json=json.dumps(key_snapshot, ensure_ascii=False),
        reason=clean_reason[:300],
        triggered_by=teacher_id,
        created_at=now,
    )
    db.add(grade_run)
    db.flush()

    submissions = (
        db.execute(
            select(Submission)
            .where(Submission.exam_id == exam.id)
            .order_by(Submission.submitted_at.asc())
        )
        .scalars()
        .all()
    )
    classroom = db.get(Classroom, exam.classroom_id)
    classroom_name = classroom.name if classroom else ""

    before_scores: dict[str, float] = {}
    after_scores: dict[str, float] = {}
    receipts_updated = 0

    for sub in submissions:
        snapshot_answers: dict[str, list[str]] = json.loads(sub.answer_snapshot_json)
        outcome = score_submission_answers(snapshot_answers, specs)
        breakdown_payload = [
            {
                "question_version_id": item.question_version_id,
                "position": item.position,
                "weight": item.weight,
                "selected_option_ids": item.selected_option_ids,
                "correct_option_ids": item.correct_option_ids,
                "is_correct": item.is_correct,
                "earned_points": item.earned_points,
            }
            for item in outcome.breakdown
        ]

        prev_sv = db.execute(
            select(ScoreVersion)
            .where(ScoreVersion.submission_id == sub.id, ScoreVersion.is_current.is_(True))
            .order_by(ScoreVersion.version.desc())
            .limit(1)
        ).scalar_one_or_none()

        if prev_sv is not None:
            before_scores[sub.student_id] = prev_sv.score_10
            prev_sv.is_current = False
            next_sv_version = prev_sv.version + 1
            supersedes_id = prev_sv.id
        else:
            next_sv_version = 1
            supersedes_id = None

        sv = ScoreVersion(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            submission_id=sub.id,
            attempt_id=sub.attempt_id,
            student_id=sub.student_id,
            grade_run_id=grade_run.id,
            version=next_sv_version,
            raw_correct=outcome.raw_correct,
            total_questions=outcome.total_questions,
            max_points=outcome.max_points,
            earned_points=outcome.earned_points,
            score_10=outcome.score_10,
            breakdown_json=json.dumps(breakdown_payload, ensure_ascii=False),
            reason=clean_reason[:300],
            supersedes_id=supersedes_id,
            is_current=True,
            created_at=now,
        )
        db.add(sv)
        db.flush()
        after_scores[sub.student_id] = sv.score_10

        # Supersede published receipt cleanly if exam is already PUBLISHED and score/key changed
        needs_new_receipt = (
            exam.status == "PUBLISHED"
            and settings is not None
            and (
                prev_sv is None
                or prev_sv.score_10 != sv.score_10
                or prev_sv.breakdown_json != sv.breakdown_json
                or bool(updated_keys)
            )
        )
        if needs_new_receipt and settings is not None:
            student_row = db.get(Student, sub.student_id)
            if student_row is not None:
                generate_and_save_receipt_version(
                    db,
                    settings=settings,
                    exam=exam,
                    classroom_name=classroom_name,
                    student=student_row,
                    submission=sub,
                    score_version=sv,
                    now=now,
                )
                receipts_updated += 1

    action_name = "REGRADE_EXAM" if next_run_number > 1 else "RUN_GRADING"
    if exam.status == "PUBLISHED" and next_run_number > 1:
        action_name = "REGRADE_AFTER_PUBLISH"

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action=action_name,
        target_type="exam",
        target_id=exam.id,
        before_hash=_hash_canonical(before_scores) if before_scores else "",
        after_hash=_hash_canonical(after_scores),
        details={
            "grade_run_id": grade_run.id,
            "run_number": next_run_number,
            "reason": clean_reason[:300],
            "graded_count": len(submissions),
            "receipts_updated": receipts_updated,
        },
    )
    return grade_run, len(submissions), receipts_updated


def run_grading_for_exam(
    db: Session,
    *,
    exam_id: str,
    teacher_id: int,
    reason: str,
    updated_keys: dict[str, list[str]] | None = None,
    settings: Settings | None = None,
) -> tuple[GradeRun, int, int]:
    with EXAM_WRITE_LOCK:
        exam = db.get(Exam, exam_id)
        if exam is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
        if exam.status not in {"CLOSED", "REVIEWED", "PUBLISHED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ có thể chấm điểm khi phòng thi đã đóng (CLOSED / REVIEWED / PUBLISHED).",
            )
        grade_run, scored_count, receipts_updated = _execute_grade_run_locked(
            db,
            exam=exam,
            teacher_id=teacher_id,
            reason=reason,
            updated_keys=updated_keys,
            settings=settings,
        )
        db.commit()
        db.refresh(grade_run)
        return grade_run, scored_count, receipts_updated


def review_exam_results(
    db: Session,
    *,
    exam_id: str,
    teacher_id: int,
    reason: str = "Giáo viên kiểm tra và xác nhận kết quả",
) -> Exam:
    with EXAM_WRITE_LOCK:
        exam = db.get(Exam, exam_id)
        if exam is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
        if exam.status not in {"CLOSED", "REVIEWED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Không thể duyệt kết quả khi kỳ thi đang ở trạng thái {exam.status}.",
            )

        # Ensure every submission has a current ScoreVersion
        existing_sub_ids = set(
            db.execute(select(Submission.id).where(Submission.exam_id == exam.id)).scalars().all()
        )
        scored_sub_ids = set(
            db.execute(
                select(ScoreVersion.submission_id).where(
                    ScoreVersion.exam_id == exam.id,
                    ScoreVersion.is_current.is_(True),
                )
            )
            .scalars()
            .all()
        )
        has_run = db.execute(
            select(GradeRun.id).where(GradeRun.exam_id == exam.id).limit(1)
        ).scalar_one_or_none()
        if has_run is None or not existing_sub_ids.issubset(scored_sub_ids):
            _execute_grade_run_locked(
                db,
                exam=exam,
                teacher_id=teacher_id,
                reason="Chấm điểm hoàn tất trước bước duyệt",
            )

        now = datetime.now(UTC)
        if exam.status == "CLOSED":
            exam.status = "REVIEWED"
            exam.reviewed_at = now
            record_audit_event(
                db,
                actor_type="teacher",
                actor_id=str(teacher_id),
                action="REVIEW_EXAM_RESULTS",
                target_type="exam",
                target_id=exam.id,
                details={
                    "reason": reason.strip() or "Xác nhận kết quả",
                    "submission_count": len(existing_sub_ids),
                },
            )
        db.commit()
        db.refresh(exam)
        return exam


def publish_exam_results(
    db: Session,
    *,
    exam_id: str,
    teacher_id: int,
    settings: Settings,
) -> tuple[Exam, int]:
    """Enforce CLOSED -> REVIEWED -> PUBLISHED gate strictly and issue receipts."""
    with EXAM_WRITE_LOCK:
        exam = db.get(Exam, exam_id)
        if exam is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
        if exam.status == "PUBLISHED":
            cnt = int(
                db.execute(
                    select(func.count())
                    .select_from(ReceiptVersion)
                    .where(ReceiptVersion.exam_id == exam.id, ReceiptVersion.is_current.is_(True))
                ).scalar_one()
            )
            return exam, cnt
        if exam.status != "REVIEWED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vui lòng thực hiện bước Duyệt kết quả (REVIEWED) trước khi công bố.",
            )

        existing_sub_ids = set(
            db.execute(select(Submission.id).where(Submission.exam_id == exam.id)).scalars().all()
        )
        scored_sub_ids = set(
            db.execute(
                select(ScoreVersion.submission_id).where(
                    ScoreVersion.exam_id == exam.id,
                    ScoreVersion.is_current.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not existing_sub_ids.issubset(scored_sub_ids):
            _execute_grade_run_locked(
                db,
                exam=exam,
                teacher_id=teacher_id,
                reason="Chấm hoàn tất trước công bố",
            )

        now = datetime.now(UTC)
        classroom = db.get(Classroom, exam.classroom_id)
        classroom_name = classroom.name if classroom else ""

        current_scores = (
            db.execute(
                select(ScoreVersion).where(
                    ScoreVersion.exam_id == exam.id,
                    ScoreVersion.is_current.is_(True),
                )
            )
            .scalars()
            .all()
        )
        issued_count = 0
        published_digest: dict[str, Any] = {}
        for sv in current_scores:
            student_row = db.get(Student, sv.student_id)
            sub_row = db.get(Submission, sv.submission_id)
            if student_row is None or sub_row is None:
                continue
            receipt = generate_and_save_receipt_version(
                db,
                settings=settings,
                exam=exam,
                classroom_name=classroom_name,
                student=student_row,
                submission=sub_row,
                score_version=sv,
                now=now,
            )
            issued_count += 1
            published_digest[student_row.roster_code] = {
                "score_10": sv.score_10,
                "receipt_version": receipt.version,
                "sha256": receipt.document_sha256,
            }

        exam.status = "PUBLISHED"
        exam.published_at = now
        record_audit_event(
            db,
            actor_type="teacher",
            actor_id=str(teacher_id),
            action="PUBLISH_EXAM_RESULTS",
            target_type="exam",
            target_id=exam.id,
            after_hash=_hash_canonical(published_digest),
            details={"receipts_issued": issued_count, "published_at": now.isoformat()},
        )
        db.commit()
        db.refresh(exam)
        return exam, issued_count


def _status_label_vi(attempt: Attempt | None, submission: Submission | None) -> str:
    if submission is not None:
        if submission.submission_mode == "teacher_close_auto":
            return "Khóa tự động khi đóng phòng"
        if submission.submission_mode == "teacher_terminate_review":
            return "Kết thúc sau xác minh"
        return "Đã nộp bài"
    if attempt is None:
        return "Chưa vào phòng"
    if attempt.state == "ENDED_WITH_REVIEW":
        return "Kết thúc sau xác minh (chưa nộp)"
    if attempt.state == "LOCKED_PENDING_REVIEW":
        return "Đang tạm khóa chưa xử lý"
    return f"Chưa hoàn thành ({attempt.state})"


def get_teacher_exam_results_overview(db: Session, *, exam_id: str) -> dict[str, Any]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    classroom = db.get(Classroom, exam.classroom_id)

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
    attempts = {
        a.student_id: a
        for a in db.execute(select(Attempt).where(Attempt.exam_id == exam.id)).scalars().all()
    }
    submissions = {
        s.student_id: s
        for s in db.execute(select(Submission).where(Submission.exam_id == exam.id)).scalars().all()
    }
    scores = {
        sv.student_id: sv
        for sv in db.execute(
            select(ScoreVersion).where(
                ScoreVersion.exam_id == exam.id, ScoreVersion.is_current.is_(True)
            )
        )
        .scalars()
        .all()
    }
    receipts = {
        rv.student_id: rv
        for rv in db.execute(
            select(ReceiptVersion).where(
                ReceiptVersion.exam_id == exam.id, ReceiptVersion.is_current.is_(True)
            )
        )
        .scalars()
        .all()
    }
    open_incidents_by_attempt = dict(
        db.execute(
            select(Incident.attempt_id, func.count(Incident.id))
            .where(Incident.exam_id == exam.id, Incident.state == "OPEN")
            .group_by(Incident.attempt_id)
        ).all()
    )

    student_rows: list[dict[str, Any]] = []
    graded_scores: list[float] = []
    unresolved_attempts = 0
    for st in students:
        att = attempts.get(st.id)
        sub = submissions.get(st.id)
        sv = scores.get(st.id)
        rv = receipts.get(st.id)
        if att is not None and sub is None:
            unresolved_attempts += 1
        if sv is not None:
            graded_scores.append(sv.score_10)

        student_rows.append(
            {
                "student_id": st.id,
                "roster_code": st.roster_code,
                "full_name": st.full_name,
                "attempt_id": att.id if att else None,
                "attempt_state": att.state if att else "NOT_JOINED",
                "status_label": _status_label_vi(att, sub),
                "submission_id": sub.id if sub else None,
                "submitted_at": sub.submitted_at.isoformat() if sub else None,
                "snapshot_hash": sub.snapshot_hash if sub else None,
                "raw_correct": sv.raw_correct if sv else None,
                "total_questions": sv.total_questions if sv else None,
                "earned_points": sv.earned_points if sv else None,
                "max_points": sv.max_points if sv else None,
                "score_10": sv.score_10 if sv else None,
                "score_version": sv.version if sv else 0,
                "regrade_count": max(0, sv.version - 1) if sv else 0,
                "receipt_code": rv.receipt_code if rv else None,
                "receipt_version": rv.version if rv else 0,
                "open_incidents": int(open_incidents_by_attempt.get(att.id, 0)) if att else 0,
            }
        )

    runs = (
        db.execute(
            select(GradeRun).where(GradeRun.exam_id == exam.id).order_by(GradeRun.run_number.desc())
        )
        .scalars()
        .all()
    )

    exam_qs = (
        db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.position.asc())
        )
        .scalars()
        .all()
    )
    qvids = [eq.question_version_id for eq in exam_qs]
    qvs = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(qvids)))
        .scalars()
        .all()
    } if qvids else {}

    question_keys: list[dict[str, Any]] = []
    for eq in exam_qs:
        qv = qvs.get(eq.question_version_id)
        if qv is None:
            continue
        key_versions = (
            db.execute(
                select(AnswerKeyVersion)
                .where(AnswerKeyVersion.question_version_id == qv.id)
                .order_by(AnswerKeyVersion.version_number.desc(), AnswerKeyVersion.approved_at.desc())
            )
            .scalars()
            .all()
        )
        current_kv = key_versions[0] if key_versions else None
        question_keys.append(
            {
                "position": eq.position,
                "question_version_id": qv.id,
                "weight": eq.weight,
                "blocks": json.loads(qv.content_blocks_json),
                "options": json.loads(qv.options_json),
                "correct_option_ids": (
                    json.loads(current_kv.correct_option_ids_json) if current_kv else []
                ),
                "key_version_number": current_kv.version_number if current_kv else 1,
                "key_history": [
                    {
                        "id": kv.id,
                        "version_number": kv.version_number,
                        "correct_option_ids": json.loads(kv.correct_option_ids_json),
                        "reason": kv.reason,
                        "approved_at": kv.approved_at.isoformat(),
                    }
                    for kv in key_versions
                ],
            }
        )

    stats = compute_exam_statistics(graded_scores, len(students))
    return {
        "exam": {
            "exam_id": exam.id,
            "classroom_id": exam.classroom_id,
            "classroom_name": classroom.name if classroom else "",
            "room_code": exam.room_code,
            "title": exam.title,
            "status": exam.status,
            "closed_at": exam.closed_at.isoformat() if exam.closed_at else None,
            "reviewed_at": exam.reviewed_at.isoformat() if exam.reviewed_at else None,
            "published_at": exam.published_at.isoformat() if exam.published_at else None,
            "unresolved_attempts": unresolved_attempts,
            "question_count": len(exam_qs),
        },
        "stats": stats,
        "students": student_rows,
        "grade_runs": [
            {
                "id": gr.id,
                "run_number": gr.run_number,
                "code_version": gr.code_version,
                "reason": gr.reason,
                "created_at": gr.created_at.isoformat(),
            }
            for gr in runs
        ],
        "questions": question_keys,
    }


def get_student_phuc_khao_trace(
    db: Session,
    *,
    exam_id: str,
    student_id: str,
) -> dict[str, Any]:
    """Build complete Phúc khảo audit trail: permutation, answer revisions, key versions, scores, events."""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh.")

    attempt = db.execute(
        select(Attempt).where(Attempt.exam_id == exam_id, Attempt.student_id == student_id)
    ).scalar_one_or_none()
    submission = db.execute(
        select(Submission).where(Submission.exam_id == exam_id, Submission.student_id == student_id)
    ).scalar_one_or_none()
    perm = db.execute(
        select(ExamPermutation).where(
            ExamPermutation.exam_id == exam_id, ExamPermutation.student_id == student_id
        )
    ).scalar_one_or_none()

    exam_qs = (
        db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.position.asc())
        )
        .scalars()
        .all()
    )
    qvids = [eq.question_version_id for eq in exam_qs]
    qvs = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(qvids)))
        .scalars()
        .all()
    } if qvids else {}

    snapshot_answers: dict[str, list[str]] = (
        json.loads(submission.answer_snapshot_json) if submission else {}
    )
    q_order: list[str] = json.loads(perm.question_order_json) if perm else qvids
    opt_order_map: dict[str, list[str]] = json.loads(perm.option_order_json) if perm else {}

    revisions: list[AnswerRevision] = []
    presence_events: list[PresenceEvent] = []
    incidents: list[Incident] = []
    if attempt is not None:
        revisions = list(
            db.execute(
                select(AnswerRevision)
                .where(AnswerRevision.attempt_id == attempt.id)
                .order_by(AnswerRevision.revision.asc())
            )
            .scalars()
            .all()
        )
        presence_events = list(
            db.execute(
                select(PresenceEvent)
                .where(PresenceEvent.attempt_id == attempt.id)
                .order_by(PresenceEvent.server_time.asc())
            )
            .scalars()
            .all()
        )
        incidents = list(
            db.execute(
                select(Incident)
                .where(Incident.attempt_id == attempt.id)
                .order_by(Incident.opened_at.asc())
            )
            .scalars()
            .all()
        )

    score_versions = list(
        db.execute(
            select(ScoreVersion)
            .where(ScoreVersion.exam_id == exam_id, ScoreVersion.student_id == student_id)
            .order_by(ScoreVersion.version.desc())
        )
        .scalars()
        .all()
    )
    receipt_versions = list(
        db.execute(
            select(ReceiptVersion)
            .where(ReceiptVersion.exam_id == exam_id, ReceiptVersion.student_id == student_id)
            .order_by(ReceiptVersion.version.desc())
        )
        .scalars()
        .all()
    )

    latest_sv = score_versions[0] if score_versions else None
    breakdown_map: dict[str, dict[str, Any]] = {}
    if latest_sv is not None:
        for item in json.loads(latest_sv.breakdown_json):
            breakdown_map[str(item["question_version_id"])] = item

    question_trace: list[dict[str, Any]] = []
    for seen_pos, qvid in enumerate(q_order, start=1):
        qv = qvs.get(qvid)
        if qv is None:
            continue
        kv = _latest_key_version_for_qvid(db, qvid)
        correct_ids = list(json.loads(kv.correct_option_ids_json)) if kv else []
        raw_options = json.loads(qv.options_json)
        opt_by_id = {str(o["option_id"]): o for o in raw_options}
        seen_opt_ids = opt_order_map.get(qvid, list(opt_by_id.keys()))
        selected_ids = snapshot_answers.get(qvid, [])
        b_item = breakdown_map.get(qvid)

        seen_options = []
        for o_idx, oid in enumerate(seen_opt_ids):
            if oid not in opt_by_id:
                continue
            label = OPTION_LETTERS[o_idx] if o_idx < len(OPTION_LETTERS) else str(o_idx + 1)
            seen_options.append(
                {
                    "option_id": oid,
                    "seen_label": label,
                    "original_label": opt_by_id[oid]["label"],
                    "blocks": opt_by_id[oid]["blocks"],
                    "selected": oid in selected_ids,
                    "is_correct_option": oid in correct_ids,
                }
            )

        question_trace.append(
            {
                "seen_position": seen_pos,
                "question_version_id": qvid,
                "blocks": json.loads(qv.content_blocks_json),
                "options": seen_options,
                "selected_option_ids": selected_ids,
                "correct_option_ids": correct_ids,
                "key_version_number": kv.version_number if kv else 1,
                "is_correct": bool(b_item["is_correct"])
                if b_item
                else (bool(correct_ids) and set(selected_ids) == set(correct_ids)),
            }
        )

    related_targets = {exam_id, student_id}
    if attempt is not None:
        related_targets.add(attempt.id)
    if submission is not None:
        related_targets.add(submission.id)
    audit_events = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.target_id.in_(list(related_targets)))
            .order_by(AuditEvent.id.asc())
        )
        .scalars()
        .all()
    )

    return {
        "exam": {
            "exam_id": exam.id,
            "room_code": exam.room_code,
            "title": exam.title,
            "status": exam.status,
            "seed": exam.seed,
        },
        "student": {
            "student_id": student.id,
            "roster_code": student.roster_code,
            "full_name": student.full_name,
        },
        "attempt": (
            {
                "attempt_id": attempt.id,
                "state": attempt.state,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                "latest_revision": attempt.latest_revision,
                "reconnect_count": attempt.reconnect_count,
                "hidden_event_count": attempt.hidden_event_count,
                "extra_time_s": attempt.extra_time_s,
            }
            if attempt
            else None
        ),
        "submission": (
            {
                "submission_id": submission.id,
                "submission_mode": submission.submission_mode,
                "snapshot_hash": submission.snapshot_hash,
                "submitted_at": submission.submitted_at.isoformat(),
                "answer_snapshot": snapshot_answers,
            }
            if submission
            else None
        ),
        "permutation_seed": perm.seed if perm else None,
        "questions": question_trace,
        "answer_revisions": [
            {
                "revision": r.revision,
                "question_version_id": r.question_version_id,
                "selected_option_ids": json.loads(r.selected_option_ids_json),
                "idempotency_key": r.idempotency_key,
                "committed_at": r.committed_at.isoformat(),
            }
            for r in revisions
        ],
        "score_versions": [
            {
                "id": sv.id,
                "version": sv.version,
                "score_10": sv.score_10,
                "raw_correct": sv.raw_correct,
                "total_questions": sv.total_questions,
                "earned_points": sv.earned_points,
                "max_points": sv.max_points,
                "reason": sv.reason,
                "supersedes_id": sv.supersedes_id,
                "is_current": sv.is_current,
                "created_at": sv.created_at.isoformat(),
            }
            for sv in score_versions
        ],
        "receipt_versions": [
            {
                "id": rv.id,
                "receipt_code": rv.receipt_code,
                "version": rv.version,
                "document_sha256": rv.document_sha256,
                "supersedes_id": rv.supersedes_id,
                "is_current": rv.is_current,
                "published_at": rv.published_at.isoformat(),
            }
            for rv in receipt_versions
        ],
        "presence_events": [
            {
                "id": pe.id,
                "event_type": pe.event_type,
                "server_time": pe.server_time.isoformat(),
                "details": json.loads(pe.details_json),
            }
            for pe in presence_events
        ],
        "incidents": [
            {
                "id": inc.id,
                "state": inc.state,
                "trigger_type": inc.trigger_type,
                "summary": inc.summary,
                "opened_at": inc.opened_at.isoformat(),
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
                "resolution_reason": inc.resolution_reason,
            }
            for inc in incidents
        ],
        "audit_events": [
            {
                "id": ev.id,
                "actor_type": ev.actor_type,
                "actor_id": ev.actor_id,
                "action": ev.action,
                "target_type": ev.target_type,
                "target_id": ev.target_id,
                "before_hash": ev.before_hash,
                "after_hash": ev.after_hash,
                "event_hash": ev.event_hash,
                "created_at": ev.created_at.isoformat(),
                "details": json.loads(ev.details_json),
            }
            for ev in audit_events
        ],
    }


def _require_published_student_context(
    db: Session,
    *,
    student: StudentPrincipal,
    target_attempt_id: str | None = None,
) -> tuple[Exam, Attempt, Student]:
    if target_attempt_id is not None and target_attempt_id != student.attempt_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập kết quả của học sinh khác.",
        )
    attempt = db.get(Attempt, student.attempt_id)
    if attempt is None or attempt.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm bài.")
    if attempt.session_id != student.session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên thiết bị đã bị giáo viên đặt lại.",
        )
    exam = db.get(Exam, attempt.exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    # ZERO EARLY DISCLOSURE GATE!
    if exam.status != "PUBLISHED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kết quả và đáp án chỉ mở sau khi giáo viên công bố kết quả toàn lớp.",
        )
    st = db.get(Student, attempt.student_id)
    if st is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin học sinh.")
    return exam, attempt, st


def get_student_published_result(
    db: Session,
    *,
    student: StudentPrincipal,
    target_attempt_id: str | None = None,
) -> dict[str, Any]:
    exam, attempt, st = _require_published_student_context(
        db,
        student=student,
        target_attempt_id=target_attempt_id,
    )

    submission = db.execute(
        select(Submission).where(Submission.attempt_id == attempt.id)
    ).scalar_one_or_none()
    sv = db.execute(
        select(ScoreVersion)
        .where(ScoreVersion.attempt_id == attempt.id, ScoreVersion.is_current.is_(True))
        .order_by(ScoreVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if submission is None or sv is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy bản nộp bài hoặc kết quả chấm cho thí sinh này.",
        )

    receipt = db.execute(
        select(ReceiptVersion)
        .where(
            ReceiptVersion.exam_id == exam.id,
            ReceiptVersion.student_id == st.id,
            ReceiptVersion.is_current.is_(True),
        )
        .order_by(ReceiptVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    grade_run = db.get(GradeRun, sv.grade_run_id)
    key_snap: dict[str, Any] = json.loads(grade_run.key_snapshot_json) if grade_run else {}
    breakdown_map: dict[str, dict[str, Any]] = {
        str(b["question_version_id"]): b for b in json.loads(sv.breakdown_json)
    }

    perm = db.execute(
        select(ExamPermutation).where(
            ExamPermutation.exam_id == exam.id, ExamPermutation.student_id == st.id
        )
    ).scalar_one_or_none()
    if perm is not None:
        q_order: list[str] = json.loads(perm.question_order_json)
        opt_order_map: dict[str, list[str]] = json.loads(perm.option_order_json)
    else:
        q_order = [
            eq.question_version_id
            for eq in db.execute(
                select(ExamQuestion)
                .where(ExamQuestion.exam_id == exam.id)
                .order_by(ExamQuestion.position.asc())
            )
            .scalars()
            .all()
        ]
        opt_order_map = {}

    qvs = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(q_order)))
        .scalars()
        .all()
    } if q_order else {}

    questions_review: list[dict[str, Any]] = []
    for pos, qvid in enumerate(q_order, start=1):
        qv = qvs.get(qvid)
        if qv is None:
            continue
        b_item = breakdown_map.get(qvid, {})
        selected_ids = list(b_item.get("selected_option_ids", []))
        correct_ids = list(
            key_snap.get(qvid, {}).get("correct_option_ids")
            or b_item.get("correct_option_ids", [])
        )
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

        questions_review.append(
            {
                "position": pos,
                "question_version_id": qvid,
                "blocks": json.loads(qv.content_blocks_json),
                "options": display_options,
                "selected_option_ids": selected_ids,
                "correct_option_ids": correct_ids,
                "is_correct": bool(b_item.get("is_correct", False)),
                "earned_points": float(b_item.get("earned_points", 0.0)),
                "weight": float(b_item.get("weight", 1.0)),
            }
        )

    receipt_ver = receipt.version if receipt else sv.version
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "room_code": exam.room_code,
        "exam_status": exam.status,
        "attempt_id": attempt.id,
        "student_name": st.full_name,
        "roster_code": st.roster_code,
        "score_10": sv.score_10,
        "raw_correct": sv.raw_correct,
        "total_questions": sv.total_questions,
        "earned_points": sv.earned_points,
        "max_points": sv.max_points,
        "score_version": sv.version,
        "regrade_reason": sv.reason if sv.version > 1 else None,
        "receipt_code": receipt.receipt_code if receipt else f"EG-{exam.room_code}-{st.roster_code}",
        "receipt_version": receipt_ver,
        "superseded_previous": bool(receipt and (receipt.version > 1 or receipt.supersedes_id)),
        "document_sha256": receipt.document_sha256 if receipt else submission.snapshot_hash,
        "snapshot_hash": submission.snapshot_hash,
        "submitted_at": submission.submitted_at.isoformat(),
        "published_at": receipt.published_at.isoformat()
        if receipt
        else (exam.published_at.isoformat() if exam.published_at else None),
        "questions": questions_review,
    }


def get_student_receipt_artifact(
    db: Session,
    *,
    settings: Settings,
    student: StudentPrincipal,
    kind: Literal["pdf", "png"],
    target_attempt_id: str | None = None,
) -> tuple[bytes, str]:
    exam, attempt, st = _require_published_student_context(
        db,
        student=student,
        target_attempt_id=target_attempt_id,
    )
    receipt = db.execute(
        select(ReceiptVersion)
        .where(
            ReceiptVersion.exam_id == exam.id,
            ReceiptVersion.student_id == st.id,
            ReceiptVersion.is_current.is_(True),
        )
        .order_by(ReceiptVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if receipt is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy biên nhận kết quả cho thí sinh này.",
        )

    rel = receipt.pdf_relpath if kind == "pdf" else receipt.png_relpath
    target = (settings.receipts_dir / rel).resolve()
    if not target.is_relative_to(settings.receipts_dir.resolve()) or not target.is_file():
        raise HTTPException(status_code=404, detail="Tệp biên nhận không tồn tại trên đĩa.")
    ext = "pdf" if kind == "pdf" else "png"
    prefix = "bien_nhan" if kind == "pdf" else "the_chia_se"
    filename = sanitize_download_filename(f"{prefix}_{exam.room_code}_{st.roster_code}_v{receipt.version}")
    return target.read_bytes(), f"{filename}.{ext}"
