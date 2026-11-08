"""Exam configuration, lifecycle state controls, student paper/save/sync/submit, and backup endpoints."""

from __future__ import annotations

import json
from typing import Any

from app.api.deps import get_db
from app.db.models import Exam, ExamQuestion
from app.security.auth import (
    StudentPrincipal,
    TeacherPrincipal,
    require_student,
    require_teacher,
)
from app.services.answer_service import (
    get_canonical_sync_state,
    get_student_paper_payload,
    save_answer_revision,
    submit_student_attempt,
)
from app.services.backup_service import (
    create_full_backup,
    list_backups,
    verify_backup_archive,
)
from app.services.exam_service import (
    attach_questions_to_exam,
    cancel_exam_session,
    close_exam_session,
    compute_remaining_seconds,
    create_configured_exam,
    open_exam_waiting_room,
    pause_exam_session,
    resume_exam_session,
    start_exam_session,
)
from app.services.monitoring_service import get_room_monitoring_snapshot
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1", tags=["exams"])


class CreateExamRequest(BaseModel):
    classroom_id: str
    title: str = Field(min_length=1, max_length=200)
    duration_s: int = Field(default=900, ge=60, le=14400)
    question_version_ids: list[str] = Field(min_length=1)
    shuffle_questions: bool = True
    shuffle_options: bool = True
    seed: int | None = None
    policy: dict[str, int] | None = None
    open_waiting: bool = True
    invite_ttl_minutes: int = Field(default=120, ge=5, le=1440)


class AttachQuestionsRequest(BaseModel):
    question_version_ids: list[str] = Field(min_length=1)


class ExamControlReasonRequest(BaseModel):
    reason: str = Field(default="Giáo viên thao tác điều khiển phòng thi", max_length=300)


class ExamDetailDTO(BaseModel):
    exam_id: str
    classroom_id: str
    room_code: str
    title: str
    duration_s: int
    status: str
    question_count: int
    shuffle_questions: bool
    shuffle_options: bool
    remaining_s: int
    is_paused: bool
    start_at: str | None
    deadline_at: str | None
    closed_at: str | None
    policy: dict[str, Any]


class SaveAnswerRequest(BaseModel):
    question_version_id: str
    selected_option_ids: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=4, max_length=100)
    client_timestamp: str | None = Field(default=None, max_length=64)


class SaveAnswerResponse(BaseModel):
    status: str
    attempt_id: str
    question_version_id: str
    selected_option_ids: list[str]
    server_revision: int
    idempotency_key: str
    committed_at: str
    duplicate: bool


class SubmitAttemptResponse(BaseModel):
    submission_id: str
    attempt_id: str
    snapshot_hash: str
    submitted_at: str
    submission_mode: str
    already_submitted: bool


class BackupManifestDTO(BaseModel):
    id: str
    created_at: str
    schema_version: str
    sha256: str
    location: str
    record_counts: dict[str, int]
    verified_at: str | None


class VerifyBackupResponse(BaseModel):
    manifest_id: str | None
    archive_name: str
    schema_version: str
    checksum_valid: bool
    sqlite_integrity_ok: bool
    record_counts: dict[str, int]
    dry_run: bool


def _exam_to_dto(db: Session, exam: Exam) -> ExamDetailDTO:
    q_count = int(
        db.execute(
            select(func.count()).select_from(ExamQuestion).where(ExamQuestion.exam_id == exam.id)
        ).scalar_one()
    )
    return ExamDetailDTO(
        exam_id=exam.id,
        classroom_id=exam.classroom_id,
        room_code=exam.room_code,
        title=exam.title,
        duration_s=exam.duration_s,
        status=exam.status,
        question_count=q_count,
        shuffle_questions=exam.shuffle_questions,
        shuffle_options=exam.shuffle_options,
        remaining_s=compute_remaining_seconds(exam),
        is_paused=exam.paused_at is not None,
        start_at=exam.start_at.isoformat() if exam.start_at else None,
        deadline_at=exam.deadline_at.isoformat() if exam.deadline_at else None,
        closed_at=exam.closed_at.isoformat() if exam.closed_at else None,
        policy=json.loads(exam.policy_json or "{}"),
    )


@router.get("/exams/active", response_model=ExamDetailDTO | None)
def get_active_exam(
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO | None:
    """Return the currently active exam session (WAITING or RUNNING) if one exists."""
    active = (
        db.execute(
            select(Exam)
            .where(Exam.status.in_(["RUNNING", "WAITING"]))
            .order_by(Exam.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if active is None:
        return None
    return _exam_to_dto(db, active)


@router.get("/exams", response_model=list[ExamDetailDTO])
def list_exams(
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[ExamDetailDTO]:
    exams = db.execute(select(Exam).order_by(Exam.created_at.desc())).scalars().all()
    return [_exam_to_dto(db, ex) for ex in exams]


@router.get("/exams/{exam_id}", response_model=ExamDetailDTO)
def get_exam_detail(
    exam_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    return _exam_to_dto(db, exam)


@router.post("/exams", status_code=201)
def post_create_exam(
    payload: CreateExamRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    secret: bytes = request.app.state.server_secret
    exam, issued = create_configured_exam(
        db,
        classroom_id=payload.classroom_id,
        title=payload.title,
        duration_s=payload.duration_s,
        question_version_ids=payload.question_version_ids,
        shuffle_questions=payload.shuffle_questions,
        shuffle_options=payload.shuffle_options,
        seed=payload.seed,
        policy=payload.policy,
        teacher_id=teacher.teacher_id,
        open_waiting=payload.open_waiting,
        invite_ttl_minutes=payload.invite_ttl_minutes,
        server_secret=secret,
    )
    return {
        "exam": _exam_to_dto(db, exam).model_dump(),
        "invites": [
            {
                "student_id": inv.student_id,
                "roster_code": inv.roster_code,
                "full_name": inv.full_name,
                "invite_code": inv.invite_code,
                "expires_at": inv.expires_at.isoformat(),
            }
            for inv in issued
        ],
    }


@router.put("/exams/{exam_id}/questions")
def put_exam_questions(
    exam_id: str,
    payload: AttachQuestionsRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    cnt = attach_questions_to_exam(
        db,
        exam_id=exam_id,
        question_version_ids=payload.question_version_ids,
        teacher_id=teacher.teacher_id,
    )
    return {"question_count": cnt}


@router.post("/exams/{exam_id}/open-waiting")
def post_open_waiting(
    exam_id: str,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    secret: bytes = request.app.state.server_secret
    exam, issued = open_exam_waiting_room(
        db,
        exam_id=exam_id,
        invite_ttl_minutes=120,
        teacher_id=teacher.teacher_id,
        server_secret=secret,
    )
    return {
        "exam": _exam_to_dto(db, exam).model_dump(),
        "invites": [
            {
                "student_id": inv.student_id,
                "roster_code": inv.roster_code,
                "full_name": inv.full_name,
                "invite_code": inv.invite_code,
                "expires_at": inv.expires_at.isoformat(),
            }
            for inv in issued
        ],
    }


async def _broadcast_exam_transition(request: Request, db: Session, exam: Exam) -> None:
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is None:
        return
    await ws_manager.broadcast_exam_state(
        exam.id,
        {
            "type": "exam_state",
            "exam_id": exam.id,
            "exam_status": exam.status,
            "is_paused": exam.paused_at is not None,
            "remaining_s": compute_remaining_seconds(exam),
        },
    )
    snap = get_room_monitoring_snapshot(db, exam_id=exam.id)
    await ws_manager.broadcast_teacher_snapshot(exam.id, snap)


@router.post("/exams/{exam_id}/start", response_model=ExamDetailDTO)
async def post_start_exam(
    exam_id: str,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO:
    exam = start_exam_session(db, exam_id=exam_id, teacher_id=teacher.teacher_id)
    await _broadcast_exam_transition(request, db, exam)
    return _exam_to_dto(db, exam)


@router.post("/exams/{exam_id}/pause", response_model=ExamDetailDTO)
async def post_pause_exam(
    exam_id: str,
    payload: ExamControlReasonRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO:
    exam = pause_exam_session(db, exam_id=exam_id, reason=payload.reason, teacher_id=teacher.teacher_id)
    await _broadcast_exam_transition(request, db, exam)
    return _exam_to_dto(db, exam)


@router.post("/exams/{exam_id}/resume", response_model=ExamDetailDTO)
async def post_resume_exam(
    exam_id: str,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO:
    exam = resume_exam_session(db, exam_id=exam_id, teacher_id=teacher.teacher_id)
    await _broadcast_exam_transition(request, db, exam)
    return _exam_to_dto(db, exam)


@router.post("/exams/{exam_id}/close", response_model=ExamDetailDTO)
async def post_close_exam(
    exam_id: str,
    request: Request,
    payload: ExamControlReasonRequest | None = None,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO:
    reason = payload.reason if payload else "Giáo viên đóng phòng thu bài"
    exam = close_exam_session(db, exam_id=exam_id, reason=reason, teacher_id=teacher.teacher_id)
    await _broadcast_exam_transition(request, db, exam)
    return _exam_to_dto(db, exam)


@router.post("/exams/{exam_id}/cancel", response_model=ExamDetailDTO)
async def post_cancel_exam(
    exam_id: str,
    request: Request,
    payload: ExamControlReasonRequest | None = None,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ExamDetailDTO:
    reason = payload.reason if payload else "Giáo viên hủy phòng chờ"
    exam = cancel_exam_session(db, exam_id=exam_id, reason=reason, teacher_id=teacher.teacher_id)
    await _broadcast_exam_transition(request, db, exam)
    return _exam_to_dto(db, exam)



# --- Student Exam Execution Endpoints (STRICTLY NO ANSWER KEY LEAK!) ---


@router.get("/attempts/me/paper")
def get_my_paper(
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_student_paper_payload(db, student=student)


@router.post("/attempts/{attempt_id}/answers", response_model=SaveAnswerResponse)
def post_save_answer(
    attempt_id: str,
    payload: SaveAnswerRequest,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> SaveAnswerResponse:
    ack = save_answer_revision(
        db,
        attempt_id=attempt_id,
        student=student,
        question_version_id=payload.question_version_id,
        selected_option_ids=payload.selected_option_ids,
        idempotency_key=payload.idempotency_key,
        client_timestamp=payload.client_timestamp,
    )
    return SaveAnswerResponse(
        status="saved",
        attempt_id=ack.attempt_id,
        question_version_id=ack.question_version_id,
        selected_option_ids=ack.selected_option_ids,
        server_revision=ack.server_revision,
        idempotency_key=ack.idempotency_key,
        committed_at=ack.committed_at.isoformat(),
        duplicate=ack.duplicate,
    )


@router.get("/attempts/{attempt_id}/sync")
def get_attempt_sync(
    attempt_id: str,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_canonical_sync_state(db, attempt_id=attempt_id, student=student)


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitAttemptResponse)
async def post_submit_attempt(
    attempt_id: str,
    request: Request,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> SubmitAttemptResponse:
    res = submit_student_attempt(db, attempt_id=attempt_id, student=student)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None and not res.already_submitted:
        snap = get_room_monitoring_snapshot(db, exam_id=student.exam_id)
        await ws_manager.broadcast_teacher_snapshot(student.exam_id, snap)
    return SubmitAttemptResponse(
        submission_id=res.submission.id,
        attempt_id=res.submission.attempt_id,
        snapshot_hash=res.submission.snapshot_hash,
        submitted_at=res.submission.submitted_at.isoformat(),
        submission_mode=res.submission.submission_mode,
        already_submitted=res.already_submitted,
    )


# --- Backup & Recovery Endpoints (Teacher only) ---


@router.get("/system/backups", response_model=list[BackupManifestDTO])
def get_backups_list(
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[BackupManifestDTO]:
    return [
        BackupManifestDTO(
            id=m.id,
            created_at=m.created_at.isoformat(),
            schema_version=m.schema_version,
            sha256=m.sha256,
            location=m.location,
            record_counts=json.loads(m.record_counts_json or "{}"),
            verified_at=m.verified_at.isoformat() if m.verified_at else None,
        )
        for m in list_backups(db)
    ]


@router.post("/system/backups", response_model=BackupManifestDTO, status_code=201)
def post_create_backup(
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> BackupManifestDTO:
    m = create_full_backup(
        db,
        settings=request.app.state.settings,
        teacher_id=teacher.teacher_id,
    )
    return BackupManifestDTO(
        id=m.id,
        created_at=m.created_at.isoformat(),
        schema_version=m.schema_version,
        sha256=m.sha256,
        location=m.location,
        record_counts=json.loads(m.record_counts_json or "{}"),
        verified_at=m.verified_at.isoformat() if m.verified_at else None,
    )


@router.post("/system/backups/{backup_id}/verify", response_model=VerifyBackupResponse)
def post_verify_backup_dry_run(
    backup_id: str,
    request: Request,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> VerifyBackupResponse:
    report = verify_backup_archive(db, settings=request.app.state.settings, backup_id=backup_id)
    return VerifyBackupResponse(
        manifest_id=report.manifest_id,
        archive_name=report.archive_name,
        schema_version=report.schema_version,
        checksum_valid=report.checksum_valid,
        sqlite_integrity_ok=report.sqlite_integrity_ok,
        record_counts=report.record_counts,
        dry_run=report.dry_run,
    )
