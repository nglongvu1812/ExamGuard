"""Teacher grading/regrade/publish/export/audit APIs and gated student result/receipt endpoints."""

from __future__ import annotations

import json
from typing import Any

from app.api.deps import get_db
from app.db.models import AuditEvent, Exam
from app.security.auth import (
    StudentPrincipal,
    TeacherPrincipal,
    require_student,
    require_teacher,
)
from app.services.audit_service import verify_audit_chain
from app.services.exam_service import compute_remaining_seconds
from app.services.export_service import export_exam_grades_xlsx
from app.services.grading_service import (
    get_student_phuc_khao_trace,
    get_student_published_result,
    get_student_receipt_artifact,
    get_teacher_exam_results_overview,
    publish_exam_results,
    review_exam_results,
    run_grading_for_exam,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1", tags=["results"])


class GradeExamRequest(BaseModel):
    reason: str = Field(default="Chấm điểm tự động", max_length=300)
    updated_keys: dict[str, list[str]] | None = None


class ReviewExamRequest(BaseModel):
    reason: str = Field(default="Giáo viên đã kiểm tra và duyệt kết quả", max_length=300)


class PublishExamRequest(BaseModel):
    confirm: bool = True


async def _notify_exam_state_update(request: Request, exam: Exam, *, results_updated: bool = False) -> None:
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
            "results_updated": results_updated,
        },
    )


# --- Teacher Results, Review, Publish, Regrade, Export, Phúc khảo & Audit ---


@router.get("/results/exams/{exam_id}")
def get_teacher_results(
    exam_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_teacher_exam_results_overview(db, exam_id=exam_id)


@router.post("/results/exams/{exam_id}/grade")
async def post_grade_or_regrade(
    exam_id: str,
    payload: GradeExamRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    grade_run, scored_count, receipts_updated = run_grading_for_exam(
        db,
        exam_id=exam_id,
        teacher_id=teacher.teacher_id,
        reason=payload.reason,
        updated_keys=payload.updated_keys,
        settings=request.app.state.settings,
    )
    exam = db.get(Exam, exam_id)
    if exam is not None and exam.status == "PUBLISHED":
        await _notify_exam_state_update(request, exam, results_updated=True)
    return {
        "grade_run_id": grade_run.id,
        "run_number": grade_run.run_number,
        "scored_count": scored_count,
        "receipts_updated": receipts_updated,
        "reason": grade_run.reason,
    }


@router.post("/results/exams/{exam_id}/review")
def post_review_exam(
    exam_id: str,
    payload: ReviewExamRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    exam = review_exam_results(
        db,
        exam_id=exam_id,
        teacher_id=teacher.teacher_id,
        reason=payload.reason,
    )
    return {
        "exam_id": exam.id,
        "status": exam.status,
        "reviewed_at": exam.reviewed_at.isoformat() if exam.reviewed_at else None,
    }


@router.post("/results/exams/{exam_id}/publish")
async def post_publish_exam(
    exam_id: str,
    payload: PublishExamRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng xác nhận công bố kết quả và đáp án.",
        )
    exam, issued_count = publish_exam_results(
        db,
        exam_id=exam_id,
        teacher_id=teacher.teacher_id,
        settings=request.app.state.settings,
    )
    await _notify_exam_state_update(request, exam, results_updated=True)
    return {
        "exam_id": exam.id,
        "status": exam.status,
        "published_at": exam.published_at.isoformat() if exam.published_at else None,
        "receipts_issued": issued_count,
    }


@router.get("/results/exams/{exam_id}/export.xlsx")
def get_export_exam_xlsx(
    exam_id: str,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    overview = get_teacher_exam_results_overview(db, exam_id=exam_id)
    xlsx_bytes, filename = export_exam_grades_xlsx(
        db,
        exam_id=exam_id,
        teacher_id=teacher.teacher_id,
        overview_rows=list(overview["students"]),
    )
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/results/exams/{exam_id}/students/{student_id}/trace")
def get_student_trace(
    exam_id: str,
    student_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_student_phuc_khao_trace(db, exam_id=exam_id, student_id=student_id)


@router.get("/audit/verify")
def get_verify_audit_chain(
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    valid, count_or_bad_id = verify_audit_chain(db)
    recent = (
        db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(50))
        .scalars()
        .all()
    )
    return {
        "valid": valid,
        "event_count": count_or_bad_id if valid else len(recent),
        "broken_event_id": None if valid else count_or_bad_id,
        "limitation_note": (
            "Chuỗi hash SHA-256 giúp phát hiện chỉnh sửa thiếu đồng bộ trên CSDL; "
            "không thay thế lưu chứng từ độc lập ngoài máy chủ khi người thao tác có quyền admin hệ thống."
        ),
        "recent_events": [
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
            for ev in recent
        ],
    }


# --- Student Gated Result & Personal Receipts (STRICTLY FORBIDDEN BEFORE PUBLISHED!) ---


@router.get("/attempts/me/result")
def get_my_published_result(
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_student_published_result(db, student=student)


@router.get("/attempts/{attempt_id}/result")
def get_attempt_published_result(
    attempt_id: str,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return get_student_published_result(db, student=student, target_attempt_id=attempt_id)


@router.get("/attempts/me/receipt.pdf")
def get_my_receipt_pdf(
    request: Request,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    content, filename = get_student_receipt_artifact(
        db,
        settings=request.app.state.settings,
        student=student,
        kind="pdf",
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/attempts/me/share-card.png")
def get_my_share_card_png(
    request: Request,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> Response:
    content, filename = get_student_receipt_artifact(
        db,
        settings=request.app.state.settings,
        student=student,
        kind="png",
    )
    return Response(
        content=content,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
