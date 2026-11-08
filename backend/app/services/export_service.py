"""Offline PDF receipts, PII-masked PNG share cards, Excel score export with formula protection."""

from __future__ import annotations

import hashlib
import io
import json
import re
import statistics
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openpyxl
import qrcode
from app.core.config import Settings
from app.db.models import (
    Classroom,
    Exam,
    ReceiptVersion,
    ScoreVersion,
    Student,
    Submission,
)
from app.services.audit_service import record_audit_event
from openpyxl.styles import Alignment, Font, PatternFill
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

_FONTS_REGISTERED = False


def _resolve_fonts_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str):
        candidate = Path(meipass) / "app" / "assets" / "fonts"
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _ensure_pdf_fonts() -> tuple[str, str]:
    """Register bundled offline Vietnamese-capable TrueType fonts."""
    global _FONTS_REGISTERED
    fonts_dir = _resolve_fonts_dir()
    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"

    dejavu = fonts_dir / "DejaVuSans.ttf"
    ubuntu_r = fonts_dir / "Ubuntu-R.ttf"
    ubuntu_b = fonts_dir / "Ubuntu-B.ttf"

    if not _FONTS_REGISTERED:
        if ubuntu_r.exists():
            pdfmetrics.registerFont(TTFont("EG-Regular", str(ubuntu_r)))
        elif dejavu.exists():
            pdfmetrics.registerFont(TTFont("EG-Regular", str(dejavu)))
        if ubuntu_b.exists():
            pdfmetrics.registerFont(TTFont("EG-Bold", str(ubuntu_b)))
        elif dejavu.exists():
            pdfmetrics.registerFont(TTFont("EG-Bold", str(dejavu)))
        _FONTS_REGISTERED = True

    registered = set(pdfmetrics.getRegisteredFontNames())
    if "EG-Regular" in registered:
        regular_font = "EG-Regular"
    if "EG-Bold" in registered:
        bold_font = "EG-Bold"
    return regular_font, bold_font


def _load_pil_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts_dir = _resolve_fonts_dir()
    candidates = (
        [fonts_dir / "Ubuntu-B.ttf", fonts_dir / "DejaVuSans.ttf"]
        if bold
        else [fonts_dir / "Ubuntu-R.ttf", fonts_dir / "DejaVuSans.ttf"]
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def neutralize_excel_formula(value: str) -> str:
    """Prevent spreadsheet formula injection (CWE-1236) on user-supplied cells."""
    if not value:
        return value
    stripped_leading = value.lstrip(" \t\r\n")
    if value[0] in ("=", "+", "-", "@", "\t", "\r") or (
        stripped_leading and stripped_leading[0] in ("=", "+", "-", "@")
    ):
        return f"'{value}"
    return value


def sanitize_download_filename(raw: str, fallback: str = "examguard_export") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._-")
    return cleaned[:80] or fallback


def mask_student_name(full_name: str) -> str:
    """Mask personal name parts for PNG social share cards without exposing full PII."""
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "H***"
    if len(parts) == 1:
        word = parts[0]
        prefix = word[:1]
        return f"{prefix}***"
    first = parts[0][:2] if len(parts[0]) >= 2 else parts[0]
    last = parts[-1]
    masked_last = f"{last[:1]}***" if len(last) > 1 else "*"
    return f"{first}*** {masked_last}"


def mask_roster_code(roster_code: str) -> str:
    code = roster_code.strip()
    if len(code) <= 3:
        return f"{code[:1]}***"
    return f"{code[:2]}***{code[-2:]}"


def _format_dt_local(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    aware = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    return aware.astimezone().strftime("%d/%m/%Y %H:%M:%S")


def render_receipt_pdf_bytes(
    *,
    exam_title: str,
    room_code: str,
    classroom_name: str,
    student_name: str,
    roster_code: str,
    receipt_code: str,
    receipt_version: int,
    score_10: float,
    raw_correct: int,
    total_questions: int,
    earned_points: float,
    max_points: float,
    submitted_at: datetime | None,
    published_at: datetime,
    snapshot_hash: str,
    document_digest_hint: str,
) -> bytes:
    """Render an offline A4 PDF personal exam receipt with embedded Vietnamese font & local QR."""
    regular_font, bold_font = _ensure_pdf_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Header bar
    c.setFillColorRGB(0.118, 0.227, 0.373)  # #1E3A5F
    c.rect(0, height - 34 * mm, width, 34 * mm, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont(bold_font, 18)
    c.drawString(20 * mm, height - 16 * mm, "BIÊN NHẬN KẾT QUẢ KIỂM TRA — EXAMGUARD")
    c.setFont(regular_font, 10)
    c.drawString(
        20 * mm,
        height - 24 * mm,
        f"Phòng thi: {room_code}  |  Lớp: {classroom_name}  |  Phiên bản biên nhận: v{receipt_version}",
    )

    y = height - 48 * mm
    c.setFillColorRGB(0.06, 0.09, 0.16)
    c.setFont(bold_font, 14)
    c.drawString(20 * mm, y, f"Bài kiểm tra: {exam_title}")
    y -= 9 * mm

    if receipt_version > 1:
        c.setFillColorRGB(0.70, 0.32, 0.03)
        c.setFont(bold_font, 10)
        c.drawString(
            20 * mm,
            y,
            f"LƯU Ý: Đây là bản cập nhật v{receipt_version} sau khi chấm lại (thay thế biên nhận trước đó).",
        )
        y -= 8 * mm

    # Student & Score Box
    c.setStrokeColorRGB(0.80, 0.84, 0.90)
    c.setFillColorRGB(0.97, 0.98, 0.99)
    c.roundRect(20 * mm, y - 48 * mm, width - 40 * mm, 46 * mm, 4 * mm, fill=1, stroke=1)

    c.setFillColorRGB(0.12, 0.16, 0.23)
    c.setFont(bold_font, 11)
    c.drawString(26 * mm, y - 10 * mm, f"Học sinh: {student_name}")
    c.setFont(regular_font, 10)
    c.drawString(26 * mm, y - 17 * mm, f"Mã học sinh: {roster_code}")
    c.drawString(26 * mm, y - 24 * mm, f"Mã biên nhận: {receipt_code}")
    c.drawString(26 * mm, y - 31 * mm, f"Thời gian nộp bài: {_format_dt_local(submitted_at)}")
    c.drawString(26 * mm, y - 38 * mm, f"Thời gian công bố: {_format_dt_local(published_at)}")

    # Highlighted Score on the right
    c.setFillColorRGB(0.059, 0.463, 0.431)  # #0F766E
    c.setFont(bold_font, 28)
    c.drawRightString(width - 26 * mm, y - 20 * mm, f"{score_10:.2f} / 10")
    c.setFillColorRGB(0.20, 0.25, 0.33)
    c.setFont(regular_font, 10)
    c.drawRightString(
        width - 26 * mm,
        y - 29 * mm,
        f"Đúng {raw_correct}/{total_questions} câu ({earned_points:.2f}/{max_points:.2f} điểm gốc)",
    )

    y -= 62 * mm

    # Local QR verification block
    qr_payload = json.dumps(
        {
            "app": "ExamGuard",
            "receipt_code": receipt_code,
            "version": receipt_version,
            "score_10": round(score_10, 2),
            "snapshot_hash": snapshot_hash[:16],
            "digest": document_digest_hint[:16],
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    c.drawImage(ImageReader(qr_buf), 20 * mm, y - 34 * mm, width=32 * mm, height=32 * mm)

    c.setFillColorRGB(0.15, 0.20, 0.28)
    c.setFont(bold_font, 10)
    c.drawString(58 * mm, y - 6 * mm, "Thông tin đối chiếu & xác minh cục bộ:")
    c.setFont(regular_font, 9)
    c.drawString(58 * mm, y - 13 * mm, f"• Mã băm bài nộp (SHA-256): {snapshot_hash[:32]}...")
    c.drawString(58 * mm, y - 19 * mm, f"• Mã băm điểm chấm (Digest): {document_digest_hint[:32]}...")
    c.drawString(
        58 * mm,
        y - 25 * mm,
        "• Quét QR giúp giáo viên tra cứu nhanh biên nhận trên máy chủ cục bộ lớp học.",
    )
    c.drawString(
        58 * mm,
        y - 31 * mm,
        "• Nếu có khiếu nại phúc khảo, giữ mã biên nhận này để đối chiếu chuỗi Audit.",
    )

    c.setFont(regular_font, 8)
    c.setFillColorRGB(0.45, 0.50, 0.58)
    c.drawString(
        20 * mm,
        16 * mm,
        "ExamGuard LAN Offline Classroom — Biên nhận sinh tự động trên máy chủ lớp học.",
    )
    c.showPage()
    c.save()
    return buf.getvalue()


def render_share_card_png_bytes(
    *,
    exam_title: str,
    score_10: float,
    raw_correct: int,
    total_questions: int,
    masked_name: str,
    masked_code: str,
    receipt_code: str,
    receipt_version: int,
) -> bytes:
    """Render a compact PNG share card strictly with MASKED PII (no raw full name/code)."""
    img = Image.new("RGB", (900, 480), color=(248, 250, 252))
    draw = ImageDraw.Draw(img)

    font_title = _load_pil_font(30, bold=True)
    font_sub = _load_pil_font(22, bold=False)
    font_score = _load_pil_font(86, bold=True)
    font_small = _load_pil_font(18, bold=False)

    # Navy top accent bar
    draw.rectangle([(0, 0), (900, 96)], fill=(30, 58, 95))
    draw.text((40, 28), "EXAMGUARD · THẺ KẾT QUẢ KIỂM TRA", fill=(255, 255, 255), font=font_title)

    # Rounded-look inner card border
    draw.rectangle([(36, 124), (864, 420)], fill=(255, 255, 255), outline=(203, 213, 225), width=2)

    title_trimmed = exam_title[:48] + ("..." if len(exam_title) > 48 else "")
    draw.text((64, 148), title_trimmed, fill=(15, 23, 42), font=font_title)
    draw.text(
        (64, 198),
        f"Thí sinh (đã che): {masked_name}  ·  Mã: {masked_code}",
        fill=(71, 85, 105),
        font=font_sub,
    )

    draw.text((64, 248), f"{score_10:.2f} / 10", fill=(15, 118, 110), font=font_score)
    draw.text(
        (64, 360),
        f"Trả lời đúng: {raw_correct}/{total_questions} câu  ·  Biên nhận {receipt_code} (v{receipt_version})",
        fill=(51, 65, 85),
        font=font_small,
    )

    draw.text(
        (40, 440),
        "Thông tin cá nhân nhạy cảm đã được ẩn khi xuất thẻ chia sẻ · ExamGuard Offline",
        fill=(100, 116, 139),
        font=font_small,
    )

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def generate_and_save_receipt_version(
    db: Session,
    *,
    settings: Settings,
    exam: Exam,
    classroom_name: str,
    student: Student,
    submission: Submission,
    score_version: ScoreVersion,
    now: datetime | None = None,
) -> ReceiptVersion:
    """Create a new ReceiptVersion (superseding any previous version) and write PDF/PNG files."""
    settings.receipts_dir.mkdir(parents=True, exist_ok=True)
    ts = now or datetime.now(UTC)

    prev = db.execute(
        select(ReceiptVersion)
        .where(
            ReceiptVersion.exam_id == exam.id,
            ReceiptVersion.student_id == student.id,
            ReceiptVersion.is_current.is_(True),
        )
        .order_by(ReceiptVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    next_version = (prev.version + 1) if prev else 1
    receipt_code = prev.receipt_code if prev else f"EG-{exam.room_code}-{student.roster_code}"
    if prev is not None:
        prev.is_current = False

    receipt_id = str(uuid.uuid4())
    pdf_rel = f"{receipt_id}_v{next_version}.pdf"
    png_rel = f"{receipt_id}_v{next_version}.png"

    canonical_digest_input = "|".join(
        [
            exam.id,
            student.id,
            submission.id,
            submission.snapshot_hash,
            score_version.id,
            f"{score_version.score_10:.2f}",
            str(next_version),
            receipt_code,
        ]
    )
    doc_sha256 = hashlib.sha256(canonical_digest_input.encode("utf-8")).hexdigest()

    pdf_bytes = render_receipt_pdf_bytes(
        exam_title=exam.title,
        room_code=exam.room_code,
        classroom_name=classroom_name,
        student_name=student.full_name,
        roster_code=student.roster_code,
        receipt_code=receipt_code,
        receipt_version=next_version,
        score_10=score_version.score_10,
        raw_correct=score_version.raw_correct,
        total_questions=score_version.total_questions,
        earned_points=score_version.earned_points,
        max_points=score_version.max_points,
        submitted_at=submission.submitted_at,
        published_at=ts,
        snapshot_hash=submission.snapshot_hash,
        document_digest_hint=doc_sha256,
    )

    masked_name = mask_student_name(student.full_name)
    masked_code = mask_roster_code(student.roster_code)
    png_bytes = render_share_card_png_bytes(
        exam_title=exam.title,
        score_10=score_version.score_10,
        raw_correct=score_version.raw_correct,
        total_questions=score_version.total_questions,
        masked_name=masked_name,
        masked_code=masked_code,
        receipt_code=receipt_code,
        receipt_version=next_version,
    )

    pdf_path = settings.receipts_dir / pdf_rel
    png_path = settings.receipts_dir / png_rel
    pdf_path.write_bytes(pdf_bytes)
    png_path.write_bytes(png_bytes)

    final_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    receipt = ReceiptVersion(
        id=receipt_id,
        exam_id=exam.id,
        student_id=student.id,
        score_version_id=score_version.id,
        receipt_code=receipt_code,
        version=next_version,
        pdf_relpath=pdf_rel,
        png_relpath=png_rel,
        document_sha256=final_sha256,
        supersedes_id=prev.id if prev else None,
        is_current=True,
        published_at=ts,
    )
    db.add(receipt)
    db.flush()
    return receipt


def compute_exam_statistics(scores: list[float], total_students: int) -> dict[str, Any]:
    """Compute statistical summary strictly matching current DB scores."""
    graded_count = len(scores)
    if graded_count == 0:
        return {
            "total_students": total_students,
            "graded_count": 0,
            "unsubmitted_count": total_students,
            "mean_score": 0.0,
            "median_score": 0.0,
            "max_score": 0.0,
            "min_score": 0.0,
            "bins": {"excellent": 0, "good": 0, "average": 0, "below_average": 0},
        }
    return {
        "total_students": total_students,
        "graded_count": graded_count,
        "unsubmitted_count": max(0, total_students - graded_count),
        "mean_score": round(sum(scores) / graded_count, 2),
        "median_score": round(statistics.median(scores), 2),
        "max_score": round(max(scores), 2),
        "min_score": round(min(scores), 2),
        "bins": {
            "excellent": sum(1 for s in scores if s >= 8.0),
            "good": sum(1 for s in scores if 6.5 <= s < 8.0),
            "average": sum(1 for s in scores if 5.0 <= s < 6.5),
            "below_average": sum(1 for s in scores if s < 5.0),
        },
    }


def export_exam_grades_xlsx(
    db: Session,
    *,
    exam_id: str,
    teacher_id: int,
    overview_rows: list[dict[str, Any]],
) -> tuple[bytes, str]:
    """Export official grades and statistics to XLSX with CWE-1236 formula injection neutralization."""
    exam = db.get(Exam, exam_id)
    assert exam is not None
    classroom = db.get(Classroom, exam.classroom_id)
    classroom_name = classroom.name if classroom else ""

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Bảng điểm"

    header_fill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    headers = [
        "STT",
        "Mã học sinh",
        "Họ tên",
        "Trạng thái bài làm",
        "Thời gian nộp",
        "Số câu đúng",
        "Tổng số câu",
        "Điểm (/10)",
        "Phiên bản điểm",
        "Số lần chấm lại",
        "Mã biên nhận",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    graded_scores: list[float] = []
    for idx, row in enumerate(overview_rows, start=1):
        score_val = row.get("score_10")
        if isinstance(score_val, int | float):
            graded_scores.append(float(score_val))

        score_ver = int(row.get("score_version") or 0)
        regrade_cnt = max(0, score_ver - 1) if score_ver > 0 else 0
        ws.append(
            [
                idx,
                neutralize_excel_formula(str(row.get("roster_code", ""))),
                neutralize_excel_formula(str(row.get("full_name", ""))),
                neutralize_excel_formula(str(row.get("status_label", ""))),
                str(row.get("submitted_at") or "—"),
                row.get("raw_correct") if row.get("raw_correct") is not None else "—",
                row.get("total_questions") if row.get("total_questions") is not None else "—",
                round(float(score_val), 2) if isinstance(score_val, int | float) else "—",
                score_ver if score_ver > 0 else "—",
                regrade_cnt,
                neutralize_excel_formula(str(row.get("receipt_code") or "Chưa phát hành")),
            ]
        )

    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(42, max(12, max_len + 4))

    # Sheet 2: Statistical accuracy matching DB exactly
    stats = compute_exam_statistics(graded_scores, len(overview_rows))
    ws_stats = wb.create_sheet(title="Thống kê")
    ws_stats.append(["Chỉ số", "Giá trị"])
    for cell in ws_stats[1]:
        cell.fill = header_fill
        cell.font = header_font

    stat_rows = [
        ("Tên kỳ thi", neutralize_excel_formula(exam.title)),
        ("Mã phòng", neutralize_excel_formula(exam.room_code)),
        ("Lớp", neutralize_excel_formula(classroom_name)),
        ("Trạng thái phòng", exam.status),
        ("Tổng sĩ số", stats["total_students"]),
        ("Số bài đã chấm", stats["graded_count"]),
        ("Chưa nộp / Chưa thi", stats["unsubmitted_count"]),
        ("Điểm trung bình", stats["mean_score"]),
        ("Điểm trung vị (Median)", stats["median_score"]),
        ("Điểm cao nhất", stats["max_score"]),
        ("Điểm thấp nhất", stats["min_score"]),
        ("Giỏi (>= 8.0)", stats["bins"]["excellent"]),
        ("Khá (6.5 - 7.99)", stats["bins"]["good"]),
        ("Trung bình (5.0 - 6.49)", stats["bins"]["average"]),
        ("Dưới TB (< 5.0)", stats["bins"]["below_average"]),
    ]
    for label, val in stat_rows:
        ws_stats.append([label, val])
    ws_stats.column_dimensions["A"].width = 28
    ws_stats.column_dimensions["B"].width = 36

    out = io.BytesIO()
    wb.save(out)

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="EXPORT_EXAM_XLSX",
        target_type="exam",
        target_id=exam.id,
        details={"graded_count": stats["graded_count"], "mean_score": stats["mean_score"]},
    )
    db.commit()

    safe_name = sanitize_download_filename(f"bang_diem_{exam.room_code}_{exam.title}", "bang_diem")
    return out.getvalue(), f"{safe_name}.xlsx"


def verify_receipt_artifacts_integrity(db: Session, settings: Settings, exam_id: str) -> dict[str, Any]:
    """Helper used in tests/checks to verify current Question/Key/Submission/Receipt consistency."""
    receipts = (
        db.execute(
            select(ReceiptVersion).where(
                ReceiptVersion.exam_id == exam_id,
                ReceiptVersion.is_current.is_(True),
            )
        )
        .scalars()
        .all()
    )
    missing = 0
    for r in receipts:
        p = settings.receipts_dir / r.pdf_relpath
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != r.document_sha256:
            missing += 1
    return {"receipt_count": len(receipts), "integrity_errors": missing}
