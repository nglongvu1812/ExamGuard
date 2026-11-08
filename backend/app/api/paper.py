"""Paper exam versions, offline A4 booklet/OMR PDF download, and OMR scan review APIs (Teacher only)."""

from __future__ import annotations

import json
from typing import Any

from app.api.deps import get_db
from app.db.models import Classroom, Exam, ExamQuestion, OmrScanSubmission, PaperVersion, Student
from app.security.auth import TeacherPrincipal, require_teacher
from app.services.exam_service import ensure_aware
from app.services.export_service import sanitize_download_filename
from app.services.omr_service import confirm_omr_scan, process_and_store_omr_scan
from app.services.paper_service import (
    generate_paper_versions,
    render_omr_sheet_pdf,
    render_omr_template_png,
    render_paper_booklet_pdf,
)
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/paper", tags=["paper"])


class GeneratePaperVersionsRequest(BaseModel):
    count: int = Field(default=4, ge=1, le=16)
    start_code: int = Field(default=101, ge=100, le=980)


class ConfirmOmrScanRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=64)
    version_code: str = Field(min_length=1, max_length=16)
    confirmed_answers: dict[str, str | None]
    reason: str = Field(default="Giáo viên xác nhận phiếu tô OMR", max_length=300)


def _scan_to_dto(
    db: Session,
    scan: OmrScanSubmission,
) -> dict[str, Any]:
    student = db.get(Student, scan.student_id) if scan.student_id else None
    pv = db.get(PaperVersion, scan.paper_version_id) if scan.paper_version_id else None
    return {
        "scan_id": scan.id,
        "exam_id": scan.exam_id,
        "student_id": scan.student_id,
        "student_name": student.full_name if student else None,
        "roster_code": student.roster_code if student else None,
        "paper_version_id": scan.paper_version_id,
        "version_code": pv.version_code if pv else None,
        "roster_code_detected": scan.roster_code_detected,
        "version_code_detected": scan.version_code_detected,
        "source_sha256": scan.source_sha256,
        "detected_answers": json.loads(scan.detected_answers_json),
        "confirmed_answers": json.loads(scan.confirmed_answers_json),
        "confidence": json.loads(scan.confidence_json),
        "ambiguous_flags": json.loads(scan.ambiguous_questions_json),
        "overall_confidence": scan.overall_confidence,
        "status": scan.status,
        "linked_submission_id": scan.linked_submission_id,
        "confirmed_at": ensure_aware(scan.confirmed_at).isoformat() if scan.confirmed_at else None,
        "reason": scan.reason,
        "created_at": ensure_aware(scan.created_at).isoformat(),
    }


@router.post("/exams/{exam_id}/versions")
def post_generate_paper_versions(
    exam_id: str,
    payload: GeneratePaperVersionsRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    versions = generate_paper_versions(
        db,
        exam_id=exam_id,
        count=payload.count,
        start_code=payload.start_code,
        teacher_id=teacher.teacher_id,
    )
    return {
        "exam_id": exam_id,
        "versions": [
            {
                "id": v.id,
                "version_code": v.version_code,
                "question_count": len(json.loads(v.question_order_json)),
                "answer_key_map": json.loads(v.answer_key_map_json),
                "created_at": ensure_aware(v.created_at).isoformat(),
            }
            for v in versions
        ],
    }


@router.get("/exams/{exam_id}/versions")
def get_paper_versions(
    exam_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    versions = (
        db.execute(
            select(PaperVersion)
            .where(PaperVersion.exam_id == exam.id)
            .order_by(PaperVersion.version_code.asc())
        )
        .scalars()
        .all()
    )
    return {
        "exam_id": exam.id,
        "versions": [
            {
                "id": v.id,
                "version_code": v.version_code,
                "question_count": len(json.loads(v.question_order_json)),
                "answer_key_map": json.loads(v.answer_key_map_json),
                "created_at": ensure_aware(v.created_at).isoformat(),
            }
            for v in versions
        ],
    }


@router.get("/exams/{exam_id}/booklet.pdf")
def download_paper_booklet_pdf(
    exam_id: str,
    request: Request,
    codes: str | None = Query(default=None),
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None
    pdf_bytes = render_paper_booklet_pdf(
        db,
        exam_id=exam_id,
        settings=request.app.state.settings,
        version_codes=code_list,
    )
    fname = sanitize_download_filename(f"DeGiay_{exam.title}", "ExamGuard_Booklet")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'},
    )


@router.get("/exams/{exam_id}/omr-sheet.pdf")
def download_omr_sheet(
    exam_id: str,
    fmt: str = Query(default="pdf"),
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    classroom = db.get(Classroom, exam.classroom_id)
    cls_name = classroom.name if classroom else ""
    q_count = len(
        db.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id)).scalars().all()
    )
    if q_count <= 0:
        raise HTTPException(status_code=400, detail="Kỳ thi chưa có câu hỏi nào.")

    first_pv = (
        db.execute(
            select(PaperVersion)
            .where(PaperVersion.exam_id == exam.id)
            .order_by(PaperVersion.version_code.asc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    fname = sanitize_download_filename(f"PhieuOMR_{exam.title}", "ExamGuard_OMR")
    if fmt.lower() == "png":
        png_bytes = render_omr_template_png(
            exam_title=exam.title,
            classroom_name=cls_name,
            question_count=q_count,
        )
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{fname}.png"'},
        )

    pdf_bytes = render_omr_sheet_pdf(
        exam_title=exam.title,
        classroom_name=cls_name,
        question_count=q_count,
        sample_version_code=first_pv.version_code if first_pv else "",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'},
    )


@router.post("/exams/{exam_id}/scans", status_code=201)
async def upload_omr_scan(
    exam_id: str,
    request: Request,
    file: UploadFile = File(...),
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = await file.read()
    scan = process_and_store_omr_scan(
        db,
        exam_id=exam_id,
        filename=file.filename or "scan.png",
        content=content,
        settings=request.app.state.settings,
        teacher_id=teacher.teacher_id,
    )
    return _scan_to_dto(db, scan)


@router.get("/exams/{exam_id}/scans")
def list_omr_scans(
    exam_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    scans = (
        db.execute(
            select(OmrScanSubmission)
            .where(OmrScanSubmission.exam_id == exam.id)
            .order_by(OmrScanSubmission.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_scan_to_dto(db, s) for s in scans]


@router.get("/scans/{scan_id}/image")
def get_omr_scan_image(
    scan_id: str,
    request: Request,
    aligned: bool = Query(default=False),
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    scan = db.get(OmrScanSubmission, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu OMR.")
    settings = request.app.state.settings
    rel = scan.aligned_preview_relpath if (aligned and scan.aligned_preview_relpath) else scan.source_image_relpath
    path = (settings.scans_dir / rel).resolve()
    if not path.is_relative_to(settings.scans_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp ảnh scan trên ổ đĩa.")
    ext = path.suffix.lower()
    mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
    return Response(content=path.read_bytes(), media_type=mime)


@router.post("/scans/{scan_id}/confirm")
def post_confirm_omr_scan(
    scan_id: str,
    payload: ConfirmOmrScanRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    scan, submission_id, regraded = confirm_omr_scan(
        db,
        scan_id=scan_id,
        student_id=payload.student_id,
        version_code=payload.version_code,
        confirmed_answers=payload.confirmed_answers,
        reason=payload.reason,
        teacher_id=teacher.teacher_id,
        settings=request.app.state.settings,
    )
    dto = _scan_to_dto(db, scan)
    dto["submission_id"] = submission_id
    dto["regraded"] = regraded
    return dto
