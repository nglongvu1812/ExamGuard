"""Question bank and DOCX converter API routes (Teacher only)."""

from __future__ import annotations

import json
from typing import Any

from app.api.deps import get_db
from app.db.models import ImportJob, QuestionDraft
from app.security.auth import TeacherPrincipal, require_teacher
from app.services.question_service import (
    approve_question_draft,
    import_exam_file,
    list_approved_questions,
    update_question_draft,
)
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])


class QuestionDraftDTO(BaseModel):
    id: str
    import_job_id: str
    position: int
    question_type: str
    blocks: list[dict[str, Any]]
    options: list[dict[str, Any]]
    answer: dict[str, Any]
    source: dict[str, Any]
    warnings: list[str]
    confidence: dict[str, float]
    status: str
    approved_version_id: str | None


class ImportJobResponse(BaseModel):
    job_id: str
    status: str
    parser_version: str
    summary: dict[str, Any]
    drafts: list[QuestionDraftDTO]


class DraftUpdateRequest(BaseModel):
    blocks: list[dict[str, Any]] | None = None
    options: list[dict[str, Any]] | None = None
    correct_option_ids: list[str] | None = None


class ApproveRequest(BaseModel):
    bank_name: str = Field(default="Mặc định", max_length=120)


class ApprovedQuestionDTO(BaseModel):
    question_id: str
    version_id: str
    bank_name: str
    version_number: int
    blocks: list[dict[str, Any]]
    options: list[dict[str, Any]]
    correct_option_ids: list[str]
    approved_at: str


def _draft_to_dto(d: QuestionDraft) -> QuestionDraftDTO:
    return QuestionDraftDTO(
        id=d.id,
        import_job_id=d.import_job_id,
        position=d.position,
        question_type=d.question_type,
        blocks=json.loads(d.blocks_json),
        options=json.loads(d.options_json),
        answer=json.loads(d.answer_json),
        source=json.loads(d.source_json),
        warnings=json.loads(d.warnings_json),
        confidence=json.loads(d.confidence_json),
        status=d.status,
        approved_version_id=d.approved_version_id,
    )


@router.post("/import", response_model=ImportJobResponse, status_code=201)
async def post_import_questions(
    request: Request,
    file: UploadFile = File(...),
    profile: str = Form("auto"),
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ImportJobResponse:
    settings = request.app.state.settings
    content = await file.read()
    job, drafts = import_exam_file(
        db,
        filename=file.filename or "de_thi.docx",
        content=content,
        sources_dir=settings.sources_dir,
        assets_dir=settings.assets_dir,
        teacher_id=teacher.teacher_id,
        profile=profile,
    )
    return ImportJobResponse(
        job_id=job.id,
        status=job.status,
        parser_version=job.parser_version,
        summary=json.loads(job.summary_json),
        drafts=[_draft_to_dto(d) for d in drafts],
    )


@router.get("/import/{job_id}", response_model=ImportJobResponse)
def get_import_job(
    job_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ImportJobResponse:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên nhập đề.")
    drafts = (
        db.execute(
            select(QuestionDraft)
            .where(QuestionDraft.import_job_id == job_id)
            .order_by(QuestionDraft.position.asc())
        )
        .scalars()
        .all()
    )
    return ImportJobResponse(
        job_id=job.id,
        status=job.status,
        parser_version=job.parser_version,
        summary=json.loads(job.summary_json),
        drafts=[_draft_to_dto(d) for d in drafts],
    )


@router.patch("/drafts/{draft_id}", response_model=QuestionDraftDTO)
def patch_draft(
    draft_id: str,
    payload: DraftUpdateRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> QuestionDraftDTO:
    draft = update_question_draft(
        db,
        draft_id=draft_id,
        blocks=payload.blocks,
        options=payload.options,
        correct_option_ids=payload.correct_option_ids,
        teacher_id=teacher.teacher_id,
    )
    return _draft_to_dto(draft)


@router.post("/drafts/{draft_id}/approve")
def post_approve_draft(
    draft_id: str,
    payload: ApproveRequest | None = None,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ver = approve_question_draft(
        db,
        draft_id=draft_id,
        bank_name=payload.bank_name if payload else "Mặc định",
        teacher_id=teacher.teacher_id,
    )
    return {"question_id": ver.question_id, "version_id": ver.id, "status": "APPROVED"}


@router.post("/import/{job_id}/approve-ready")
def post_approve_ready_in_job(
    job_id: str,
    payload: ApproveRequest | None = None,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    drafts = (
        db.execute(
            select(QuestionDraft)
            .where(QuestionDraft.import_job_id == job_id, QuestionDraft.status != "APPROVED")
            .order_by(QuestionDraft.position.asc())
        )
        .scalars()
        .all()
    )
    approved = 0
    skipped = 0
    for d in drafts:
        try:
            approve_question_draft(
                db,
                draft_id=d.id,
                bank_name=payload.bank_name if payload else "Mặc định",
                teacher_id=teacher.teacher_id,
            )
            approved += 1
        except HTTPException:
            skipped += 1
    return {"approved_count": approved, "skipped_count": skipped}


@router.get("/bank", response_model=list[ApprovedQuestionDTO])
def get_question_bank(
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[ApprovedQuestionDTO]:
    items = list_approved_questions(db)
    return [
        ApprovedQuestionDTO(
            question_id=q.id,
            version_id=qv.id,
            bank_name=q.bank_name,
            version_number=qv.version_number,
            blocks=json.loads(qv.content_blocks_json),
            options=json.loads(qv.options_json),
            correct_option_ids=json.loads(kv.correct_option_ids_json),
            approved_at=qv.approved_at.isoformat(),
        )
        for q, qv, kv in items
    ]
