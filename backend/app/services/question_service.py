"""Question bank & converter orchestration: ingest, draft review, manual edit, and immutable approval."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.converters.docx_adapter import extract_docx_elements
from app.converters.ingest import store_source_file
from app.converters.pdf_adapter import extract_pdf_elements
from app.converters.segmenter import SegmentedQuestionDraft, segment_elements
from app.converters.xlsx_converter import parse_xlsx_questions
from app.db.models import (
    AnswerKeyVersion,
    ImportJob,
    Question,
    QuestionDraft,
    QuestionVersion,
)
from app.services.audit_service import record_audit_event
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session


def _persist_import_job_drafts(
    db: Session,
    *,
    filename: str,
    content: bytes,
    kind: str,
    parser_version: str,
    segmented: list[SegmentedQuestionDraft],
    diagnostics: dict[str, Any] | None,
    sources_dir: Path,
    teacher_id: int,
    audit_action: str,
) -> tuple[ImportJob, list[QuestionDraft]]:
    doc = store_source_file(
        db,
        sources_dir=sources_dir,
        filename=filename,
        content=content,
        kind=kind,
    )
    job = ImportJob(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        status="COMPLETED",
        parser_version=parser_version,
        summary_json="{}",
        error_json="[]",
    )
    db.add(job)
    db.flush()

    drafts: list[QuestionDraft] = []
    warnings_count = 0
    unknown_key_count = 0

    for item in segmented:
        if item.warnings:
            warnings_count += 1
        if not item.correct_option_ids:
            unknown_key_count += 1

        options_payload = [
            {"option_id": opt.option_id, "label": opt.label, "blocks": opt.blocks}
            for opt in item.options
        ]
        answer_payload = {
            "correct_option_ids": item.correct_option_ids,
            "status": item.answer_status,
            "provenance": item.answer_provenance,
        }
        source_payload = {
            "file_sha256": doc.sha256,
            "filename": doc.original_filename,
            "anchors": item.source_anchors,
            "raw_preview": item.raw_preview,
            "parser_version": parser_version,
        }
        draft = QuestionDraft(
            id=str(uuid.uuid4()),
            import_job_id=job.id,
            position=item.position,
            question_type="single_choice",
            blocks_json=json.dumps(item.blocks, ensure_ascii=False),
            options_json=json.dumps(options_payload, ensure_ascii=False),
            answer_json=json.dumps(answer_payload, ensure_ascii=False),
            source_json=json.dumps(source_payload, ensure_ascii=False),
            warnings_json=json.dumps(item.warnings, ensure_ascii=False),
            confidence_json=json.dumps(item.confidence, ensure_ascii=False),
            status="DRAFT",
        )
        db.add(draft)
        drafts.append(draft)

    summary: dict[str, Any] = {
        "total_questions": len(drafts),
        "warnings_count": warnings_count,
        "unknown_key_count": unknown_key_count,
        "filename": doc.original_filename,
        "sha256": doc.sha256,
        "format": kind,
    }
    if diagnostics:
        summary["diagnostics"] = diagnostics
    job.summary_json = json.dumps(summary, ensure_ascii=False)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action=audit_action,
        target_type="import_job",
        target_id=job.id,
        details=summary,
    )
    db.commit()
    return job, drafts


def import_exam_file(
    db: Session,
    *,
    filename: str,
    content: bytes,
    sources_dir: Path,
    assets_dir: Path,
    teacher_id: int,
    profile: str = "auto",
) -> tuple[ImportJob, list[QuestionDraft]]:
    ext = Path(filename or "de_thi.docx").suffix.lower().lstrip(".")
    if not ext:
        # Infer from magic bytes if filename lacks extension
        ext = "pdf" if content.lstrip(b"\xef\xbb\xbf\r\n ").startswith(b"%PDF-") else "docx"

    if ext == "docx":
        store_source_file(
            db, sources_dir=sources_dir, filename=filename, content=content, kind="docx"
        )
        elements = extract_docx_elements(content, db=db, assets_dir=assets_dir)
        segmented = segment_elements(elements)
        return _persist_import_job_drafts(
            db,
            filename=filename,
            content=content,
            kind="docx",
            parser_version="docx-v1.0",
            segmented=segmented,
            diagnostics=None,
            sources_dir=sources_dir,
            teacher_id=teacher_id,
            audit_action="IMPORT_DOCX_JOB",
        )
    if ext == "pdf":
        store_source_file(
            db, sources_dir=sources_dir, filename=filename, content=content, kind="pdf"
        )
        elements, diag = extract_pdf_elements(content, db=db, assets_dir=assets_dir)
        segmented = segment_elements(elements)
        return _persist_import_job_drafts(
            db,
            filename=filename,
            content=content,
            kind="pdf",
            parser_version="pdf-v1.0",
            segmented=segmented,
            diagnostics=diag,
            sources_dir=sources_dir,
            teacher_id=teacher_id,
            audit_action="IMPORT_PDF_JOB",
        )
    if ext == "xlsx":
        segmented, diag = parse_xlsx_questions(content, profile=profile)
        return _persist_import_job_drafts(
            db,
            filename=filename,
            content=content,
            kind="xlsx",
            parser_version="xlsx-v1.0",
            segmented=segmented,
            diagnostics=diag,
            sources_dir=sources_dir,
            teacher_id=teacher_id,
            audit_action="IMPORT_XLSX_JOB",
        )
    raise HTTPException(
        status_code=400,
        detail="Chỉ hỗ trợ file đề .docx, .pdf hoặc .xlsx.",
    )


def import_docx_exam(
    db: Session,
    *,
    filename: str,
    content: bytes,
    sources_dir: Path,
    assets_dir: Path,
    teacher_id: int,
) -> tuple[ImportJob, list[QuestionDraft]]:
    return import_exam_file(
        db,
        filename=filename if Path(filename).suffix else f"{filename}.docx",
        content=content,
        sources_dir=sources_dir,
        assets_dir=assets_dir,
        teacher_id=teacher_id,
    )


def _validate_draft_for_approval(draft: QuestionDraft) -> tuple[list[Any], list[dict[str, Any]], list[str]]:
    blocks = json.loads(draft.blocks_json)
    options = json.loads(draft.options_json)
    answer = json.loads(draft.answer_json)

    if not blocks:
        raise HTTPException(
            status_code=400,
            detail=f"Câu {draft.position} chưa có nội dung câu hỏi.",
        )
    if len(options) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Câu {draft.position} cần ít nhất 2 phương án trả lời.",
        )
    correct_ids = list(answer.get("correct_option_ids", []))
    option_ids = {opt["option_id"] for opt in options}
    if not correct_ids or any(cid not in option_ids for cid in correct_ids):
        raise HTTPException(
            status_code=400,
            detail=f"Câu {draft.position} chưa có đáp án đúng được giáo viên xác nhận.",
        )
    return blocks, options, correct_ids


def update_question_draft(
    db: Session,
    *,
    draft_id: str,
    blocks: list[dict[str, Any]] | None,
    options: list[dict[str, Any]] | None,
    correct_option_ids: list[str] | None,
    teacher_id: int,
) -> QuestionDraft:
    draft = db.get(QuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi nháp.")
    if draft.status == "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Câu hỏi đã duyệt vào ngân hàng đề (phiên bản bất biến).",
        )

    if blocks is not None:
        draft.blocks_json = json.dumps(blocks, ensure_ascii=False)
    if options is not None:
        draft.options_json = json.dumps(options, ensure_ascii=False)
    if correct_option_ids is not None:
        current_ans = json.loads(draft.answer_json)
        current_ans["correct_option_ids"] = correct_option_ids
        current_ans["status"] = "confirmed" if correct_option_ids else "unknown"
        current_ans["provenance"] = "teacher_manual_edit"
        draft.answer_json = json.dumps(current_ans, ensure_ascii=False)

    # Recompute warnings cleanly
    cur_blocks = json.loads(draft.blocks_json)
    cur_opts = json.loads(draft.options_json)
    cur_ans = json.loads(draft.answer_json)
    warnings = [
        w
        for w in json.loads(draft.warnings_json)
        if w not in {"ANSWER_NOT_FOUND", "MULTIPLE_KEYS_DETECTED", "INSUFFICIENT_OPTIONS", "EMPTY_QUESTION_BODY"}
    ]
    if not cur_blocks:
        warnings.append("EMPTY_QUESTION_BODY")
    if len(cur_opts) < 2:
        warnings.append("INSUFFICIENT_OPTIONS")
    if not cur_ans.get("correct_option_ids"):
        warnings.append("ANSWER_NOT_FOUND")
    draft.warnings_json = json.dumps(warnings, ensure_ascii=False)

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="EDIT_QUESTION_DRAFT",
        target_type="question_draft",
        target_id=draft.id,
        details={"position": draft.position},
    )
    db.commit()
    db.refresh(draft)
    return draft


def approve_question_draft(
    db: Session,
    *,
    draft_id: str,
    bank_name: str,
    teacher_id: int,
) -> QuestionVersion:
    draft = db.get(QuestionDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi nháp.")
    if draft.status == "APPROVED" and draft.approved_version_id:
        existing_ver = db.get(QuestionVersion, draft.approved_version_id)
        if existing_ver is not None:
            return existing_ver

    blocks, options, correct_ids = _validate_draft_for_approval(draft)
    now = datetime.now(UTC)

    question = Question(
        id=str(uuid.uuid4()),
        bank_name=bank_name.strip() or "Mặc định",
        created_at=now,
    )
    db.add(question)
    db.flush()

    version = QuestionVersion(
        id=str(uuid.uuid4()),
        question_id=question.id,
        version_number=1,
        content_blocks_json=json.dumps(blocks, ensure_ascii=False),
        options_json=json.dumps(options, ensure_ascii=False),
        provenance_json=draft.source_json,
        approved_by=teacher_id,
        approved_at=now,
    )
    db.add(version)
    db.flush()

    question.active_version_id = version.id

    key_ver = AnswerKeyVersion(
        id=str(uuid.uuid4()),
        question_version_id=version.id,
        correct_option_ids_json=json.dumps(correct_ids),
        approved_by=teacher_id,
        approved_at=now,
    )
    db.add(key_ver)

    draft.status = "APPROVED"
    draft.approved_version_id = version.id

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="APPROVE_QUESTION_VERSION",
        target_type="question_version",
        target_id=version.id,
        details={"question_id": question.id, "draft_id": draft.id},
    )
    db.commit()
    db.refresh(version)
    return version


def list_approved_questions(db: Session) -> list[tuple[Question, QuestionVersion, AnswerKeyVersion]]:
    questions = db.execute(select(Question).order_by(Question.created_at.desc())).scalars().all()
    results: list[tuple[Question, QuestionVersion, AnswerKeyVersion]] = []
    for q in questions:
        if not q.active_version_id:
            continue
        qv = db.get(QuestionVersion, q.active_version_id)
        if qv is None:
            continue
        kv = db.execute(
            select(AnswerKeyVersion)
            .where(AnswerKeyVersion.question_version_id == qv.id)
            .order_by(AnswerKeyVersion.version_number.desc(), AnswerKeyVersion.approved_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if kv is None:
            continue
        results.append((q, qv, kv))
    return results
