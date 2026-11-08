"""Paper exam version generation, offline A4 PDF booklets with media/math fallback, and OMR sheet rendering."""

from __future__ import annotations

import hashlib
import io
import json
import random
import re
import uuid
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from app.core.config import Settings
from app.db.models import (
    AnswerKeyVersion,
    Asset,
    Classroom,
    Exam,
    ExamQuestion,
    PaperVersion,
    QuestionVersion,
)
from app.services.audit_service import record_audit_event
from app.services.export_service import ensure_pdf_fonts, load_offline_pil_font
from app.services.omr_layout import (
    A4_HEIGHT_PT,
    A4_WIDTH_PT,
    ANS_COL1_OPTION_US,
    ANS_COL2_OPTION_US,
    ANS_LABELS,
    ANS_START_V,
    ANS_STEP_V,
    BUBBLE_RADIUS_PT,
    BUBBLE_RADIUS_PX,
    CANVAS_FID_CORNERS,
    CANVAS_FID_SIZE,
    CANVAS_H,
    CANVAS_W,
    FID_BOTTOM_Y,
    FID_LEFT_X,
    FID_RIGHT_X,
    FID_SIZE_PT,
    FID_TOP_Y,
    MAX_OMR_QUESTIONS,
    SBD_COL_US,
    VERSION_COL_US,
    iter_answer_bubbles,
    iter_sbd_bubbles,
    iter_version_bubbles,
    uv_to_canvas_px,
    uv_to_pdf_pt,
)
from fastapi import HTTPException
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph
from sqlalchemy import select
from sqlalchemy.orm import Session


def _latest_key_ids(db: Session, qvid: str) -> list[str]:
    kv = db.execute(
        select(AnswerKeyVersion)
        .where(AnswerKeyVersion.question_version_id == qvid)
        .order_by(AnswerKeyVersion.version_number.desc(), AnswerKeyVersion.approved_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if kv is None:
        return []
    return [str(x) for x in json.loads(kv.correct_option_ids_json)]


def latex_to_readable_fallback(latex: str) -> str:
    """Convert common LaTeX constructs to clean readable Unicode/text fallback for offline A4 PDF."""
    s = latex.strip()
    replacements = [
        (r"\leq", "≤"),
        (r"\geq", "≥"),
        (r"\neq", "≠"),
        (r"\approx", "≈"),
        (r"\times", "×"),
        (r"\cdot", "·"),
        (r"\pm", "±"),
        (r"\infty", "∞"),
        (r"\pi", "π"),
        (r"\alpha", "α"),
        (r"\beta", "β"),
        (r"\gamma", "γ"),
        (r"\Delta", "Δ"),
        (r"\delta", "δ"),
        (r"\theta", "θ"),
        (r"\lambda", "λ"),
        (r"\sum", "∑"),
        (r"\int", "∫"),
        (r"\to", "→"),
        (r"\rightarrow", "→"),
        (r"\lim", "lim"),
        (r"\sqrt", "√"),
    ]
    for src, dst in replacements:
        s = s.replace(src, dst)
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\(?:left|right)", "", s)
    s = s.replace("{", "(").replace("}", ")")
    return s


def generate_paper_versions(
    db: Session,
    *,
    exam_id: str,
    count: int = 4,
    start_code: int = 101,
    teacher_id: int,
) -> list[PaperVersion]:
    """Deterministically generate shuffled paper exam variants keeping canonical option_id key map."""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    if count < 1 or count > 16:
        raise HTTPException(status_code=400, detail="Số lượng mã đề phải nằm trong khoảng 1–16.")

    exam_qs = (
        db.execute(
            select(ExamQuestion)
            .where(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.position.asc())
        )
        .scalars()
        .all()
    )
    if not exam_qs:
        raise HTTPException(
            status_code=400,
            detail="Kỳ thi chưa có câu hỏi nào. Vui lòng gắn câu hỏi từ ngân hàng đề trước.",
        )
    if len(exam_qs) > MAX_OMR_QUESTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Phiếu tô OMR chuẩn hỗ trợ tối đa {MAX_OMR_QUESTIONS} câu mỗi tờ.",
        )

    qids = [eq.question_version_id for eq in exam_qs]
    qv_map = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(qids)))
        .scalars()
        .all()
    }
    key_map = {qvid: set(_latest_key_ids(db, qvid)) for qvid in qids}

    existing_by_code = {
        pv.version_code: pv
        for pv in db.execute(select(PaperVersion).where(PaperVersion.exam_id == exam.id))
        .scalars()
        .all()
    }

    result_versions: list[PaperVersion] = []
    for idx in range(count):
        code = f"{start_code + idx:03d}"
        if len(code) > 3 or not code.isdigit():
            raise HTTPException(status_code=400, detail="Mã đề OMR phải gồm đúng 3 chữ số (ví dụ 101..999).")
        if code in existing_by_code:
            result_versions.append(existing_by_code[code])
            continue

        digest = hashlib.sha256(f"{exam.seed}:{exam.id}:paper:{code}".encode()).digest()
        p_seed = int.from_bytes(digest[:8], "big")
        rng = random.Random(p_seed)

        q_order = list(qids)
        if exam.shuffle_questions and len(q_order) > 1:
            rng.shuffle(q_order)

        opt_order: dict[str, list[str]] = {}
        ans_letter_map: dict[str, list[str]] = {}

        for q_pos, qvid in enumerate(q_order, start=1):
            qv = qv_map[qvid]
            opts = json.loads(qv.options_json)
            opt_ids = [str(o["option_id"]) for o in opts]
            if exam.shuffle_options and len(opt_ids) > 1:
                rng.shuffle(opt_ids)
            opt_order[qvid] = opt_ids

            correct_set = key_map.get(qvid, set())
            letters = [
                ANS_LABELS[opt_i]
                for opt_i, oid in enumerate(opt_ids[: len(ANS_LABELS)])
                if oid in correct_set
            ]
            ans_letter_map[str(q_pos)] = letters

        pv = PaperVersion(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            version_code=code,
            seed=p_seed & 0x7FFFFFFF,
            question_order_json=json.dumps(q_order),
            option_order_json=json.dumps(opt_order),
            answer_key_map_json=json.dumps(ans_letter_map, ensure_ascii=False),
            created_by=teacher_id,
        )
        db.add(pv)
        db.flush()
        result_versions.append(pv)

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="GENERATE_PAPER_VERSIONS",
        target_type="exam",
        target_id=exam.id,
        details={"version_codes": [v.version_code for v in result_versions]},
    )
    db.commit()
    return sorted(result_versions, key=lambda v: v.version_code)


def _blocks_to_plain_segments(
    blocks: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Convert Question/Option ContentBlocks into readable text + local asset IDs."""
    text_parts: list[str] = []
    asset_ids: list[str] = []
    for blk in blocks:
        btype = blk.get("type")
        if btype == "text":
            txt = str(blk.get("text", "")).strip()
            if txt:
                text_parts.append(txt)
        elif btype == "math":
            latex = str(blk.get("latex", "")).strip()
            if latex:
                text_parts.append(latex_to_readable_fallback(latex))
            fb = blk.get("fallback_asset_id")
            if fb:
                asset_ids.append(str(fb))
        elif btype == "image":
            aid = blk.get("asset_id")
            if aid:
                asset_ids.append(str(aid))
                text_parts.append("[Xem hình minh họa]")
        elif btype == "table":
            rows = blk.get("rows", [])
            if isinstance(rows, list) and rows:
                rendered_rows = [
                    " | ".join(str(cell) for cell in row)
                    for row in rows[:6]
                    if isinstance(row, list)
                ]
                if rendered_rows:
                    text_parts.append(" / ".join(rendered_rows))
    return " ".join(text_parts).strip() or "[Nội dung câu hỏi]", asset_ids


def render_paper_booklet_pdf(
    db: Session,
    *,
    exam_id: str,
    settings: Settings,
    version_codes: list[str] | None = None,
) -> bytes:
    """Render offline A4 multi-version paper exam booklet + Answer Key sheet PDF."""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")
    classroom = db.get(Classroom, exam.classroom_id)
    classroom_name = classroom.name if classroom else ""

    stmt = select(PaperVersion).where(PaperVersion.exam_id == exam.id).order_by(PaperVersion.version_code.asc())
    versions = list(db.execute(stmt).scalars().all())
    if version_codes:
        allowed = set(version_codes)
        versions = [v for v in versions if v.version_code in allowed]
    if not versions:
        raise HTTPException(
            status_code=404,
            detail="Chưa có mã đề giấy nào. Vui lòng tạo bộ mã đề trước khi xuất PDF.",
        )

    regular_font, bold_font = ensure_pdf_fonts()
    q_style = ParagraphStyle(
        "EGPaperQ",
        fontName=regular_font,
        fontSize=10.5,
        leading=14.0,
        textColor=colors.HexColor("#0F172A"),
    )
    opt_style = ParagraphStyle(
        "EGPaperOpt",
        fontName=regular_font,
        fontSize=10.0,
        leading=13.5,
        textColor=colors.HexColor("#1E293B"),
    )

    all_qids = list(
        dict.fromkeys(
            qid
            for pv in versions
            for qid in json.loads(pv.question_order_json)
        )
    )
    qv_map = {
        qv.id: qv
        for qv in db.execute(select(QuestionVersion).where(QuestionVersion.id.in_(all_qids)))
        .scalars()
        .all()
    }
    asset_map: dict[str, Path] = {}

    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(A4_WIDTH_PT, A4_HEIGHT_PT))
    content_width = A4_WIDTH_PT - 36 * mm
    left_x = 18 * mm

    def _resolve_asset_path(aid: str) -> Path | None:
        if aid in asset_map:
            return asset_map[aid]
        row = db.get(Asset, aid)
        if row is None:
            return None
        path = (settings.assets_dir / row.relpath).resolve()
        if path.is_relative_to(settings.assets_dir.resolve()) and path.is_file():
            asset_map[aid] = path
            return path
        return None

    for pv in versions:
        page_num = 1

        def _draw_header(code: str, pno: int) -> float:
            top_y = A4_HEIGHT_PT - 18 * mm
            c.setFont(bold_font, 13)
            c.setFillColor(colors.HexColor("#0F172A"))
            c.drawString(left_x, top_y, f"ĐỀ KIỂM TRA GIẤY: {exam.title}")
            c.setFont(bold_font, 12)
            c.setFillColor(colors.HexColor("#1E3A5F"))
            c.drawRightString(A4_WIDTH_PT - 18 * mm, top_y, f"MÃ ĐỀ: {code}")

            c.setFont(regular_font, 9.5)
            c.setFillColor(colors.HexColor("#475569"))
            c.drawString(
                left_x,
                top_y - 5.5 * mm,
                f"Lớp: {classroom_name}  |  Thời gian: {max(1, round(exam.duration_s / 60))} phút  |  Trang {pno}",
            )
            if pno == 1:
                c.drawString(
                    left_x,
                    top_y - 11.5 * mm,
                    "Họ và tên học sinh: ...........................................   SBD/Mã HS: ............",
                )
                y_line = top_y - 15 * mm
            else:
                y_line = top_y - 9 * mm
            c.setStrokeColor(colors.HexColor("#CBD5E1"))
            c.line(left_x, y_line, A4_WIDTH_PT - 18 * mm, y_line)
            return float(y_line - 6 * mm)

        y = _draw_header(pv.version_code, page_num)
        q_order: list[str] = json.loads(pv.question_order_json)
        opt_order: dict[str, list[str]] = json.loads(pv.option_order_json)

        for idx, qvid in enumerate(q_order, start=1):
            qv = qv_map.get(qvid)
            if qv is None:
                continue
            stem_blocks = json.loads(qv.content_blocks_json)
            stem_text, stem_assets = _blocks_to_plain_segments(stem_blocks)
            p_stem = Paragraph(f"<b>Câu {idx}.</b> {escape(stem_text)}", q_style)
            _, stem_h = p_stem.wrap(content_width, 300 * mm)

            if y - stem_h < 32 * mm:
                c.showPage()
                page_num += 1
                y = _draw_header(pv.version_code, page_num)

            p_stem.drawOn(c, left_x, y - stem_h)
            y -= stem_h + 2.5 * mm

            for aid in stem_assets:
                ap = _resolve_asset_path(aid)
                if ap is not None:
                    try:
                        ir = ImageReader(str(ap))
                        iw, ih = ir.getSize()
                        max_w = min(content_width * 0.75, 110 * mm)
                        scale = min(max_w / max(iw, 1), 36 * mm / max(ih, 1))
                        dw, dh = iw * scale, ih * scale
                        if y - dh < 25 * mm:
                            c.showPage()
                            page_num += 1
                            y = _draw_header(pv.version_code, page_num)
                        c.drawImage(ir, left_x + 4 * mm, y - dh, width=dw, height=dh)
                        y -= dh + 2.5 * mm
                    except Exception:
                        pass

            opts_raw = {str(o["option_id"]): o for o in json.loads(qv.options_json)}
            ordered_oids = opt_order.get(qvid, list(opts_raw.keys()))
            for opt_i, oid in enumerate(ordered_oids[: len(ANS_LABELS)]):
                opt_obj = opts_raw.get(oid)
                if not opt_obj:
                    continue
                opt_txt, _ = _blocks_to_plain_segments(opt_obj.get("blocks", []))
                lbl = ANS_LABELS[opt_i]
                p_opt = Paragraph(f"<b>{lbl}.</b> {escape(opt_txt)}", opt_style)
                _, oh = p_opt.wrap(content_width - 8 * mm, 100 * mm)
                if y - oh < 20 * mm:
                    c.showPage()
                    page_num += 1
                    y = _draw_header(pv.version_code, page_num)
                p_opt.drawOn(c, left_x + 5 * mm, y - oh)
                y -= oh + 1.5 * mm

            y -= 3 * mm

        c.showPage()

    # Final page: Teacher Master Answer Key for all printed paper codes
    y = A4_HEIGHT_PT - 20 * mm
    c.setFont(bold_font, 14)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(left_x, y, f"BẢNG ĐÁP ÁN DÀNH CHO GIÁO VIÊN — {exam.title}")
    y -= 8 * mm
    c.setFont(regular_font, 9.5)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(
        left_x,
        y,
        "Lưu ý bảo mật: Tài liệu chỉ dành cho giáo viên chấm/đối chiếu sau khi kết thúc giờ thi.",
    )
    y -= 9 * mm

    for pv in versions:
        if y < 35 * mm:
            c.showPage()
            y = A4_HEIGHT_PT - 22 * mm
        c.setFont(bold_font, 11)
        c.setFillColor(colors.HexColor("#1E3A5F"))
        c.drawString(left_x, y, f"Mã đề {pv.version_code}:")
        y -= 5.5 * mm
        ans_map: dict[str, list[str]] = json.loads(pv.answer_key_map_json)
        items = [f"{qno}:{','.join(ans_map[qno]) or '?'}" for qno in sorted(ans_map.keys(), key=int)]
        line_str = "   ".join(items)
        p_key = Paragraph(escape(line_str), opt_style)
        _, kh = p_key.wrap(content_width, 100 * mm)
        p_key.drawOn(c, left_x + 4 * mm, y - kh)
        y -= kh + 6 * mm

    c.save()
    return buf.getvalue()


def render_omr_sheet_pdf(
    *,
    exam_title: str,
    classroom_name: str,
    question_count: int,
    sample_version_code: str = "",
) -> bytes:
    """Render offline A4 scannable OMR Answer Sheet matching exact OMR_LAYOUT fiducials."""
    regular_font, bold_font = ensure_pdf_fonts()
    capped_q = min(max(1, question_count), MAX_OMR_QUESTIONS)
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(A4_WIDTH_PT, A4_HEIGHT_PT))

    # 4 corner black alignment fiducials
    c.setFillColor(colors.black)
    half_fid = FID_SIZE_PT / 2.0
    for fx, fy in [
        (FID_LEFT_X, FID_TOP_Y),
        (FID_RIGHT_X, FID_TOP_Y),
        (FID_LEFT_X, FID_BOTTOM_Y),
        (FID_RIGHT_X, FID_BOTTOM_Y),
    ]:
        c.rect(fx - half_fid, fy - half_fid, FID_SIZE_PT, FID_SIZE_PT, stroke=0, fill=1)

    # Header block inside safe inner region
    title_x, title_y = uv_to_pdf_pt(0.04, 0.03)
    c.setFont(bold_font, 13)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(title_x, title_y, f"PHIẾU TRẢ LỜI TRẮC NGHIỆM (OMR) — {exam_title}")

    sub_x, sub_y = uv_to_pdf_pt(0.04, 0.065)
    c.setFont(regular_font, 9.5)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(
        sub_x,
        sub_y,
        f"Lớp: {classroom_name}   |   Số câu: {capped_q}   |   Lưu ý: Tô kín đậm ô tròn bằng bút mực tối màu",
    )

    name_x, name_y = uv_to_pdf_pt(0.04, 0.105)
    c.drawString(
        name_x,
        name_y,
        "Họ và tên: ..................................................   Chữ ký HS: ...................",
    )

    # Left instruction box
    inst_x1, inst_y1 = uv_to_pdf_pt(0.04, 0.405)
    inst_x2, inst_y2 = uv_to_pdf_pt(0.41, 0.145)
    c.setStrokeColor(colors.HexColor("#94A3B8"))
    c.setLineWidth(0.75)
    c.rect(inst_x1, inst_y1, inst_x2 - inst_x1, inst_y2 - inst_y1, stroke=1, fill=0)

    c.setFont(bold_font, 10)
    c.setFillColor(colors.HexColor("#1E3A5F"))
    c.drawString(inst_x1 + 8, inst_y2 - 18, "HƯỚNG DẪN TÔ PHIẾU:")
    c.setFont(regular_font, 8.8)
    c.setFillColor(colors.HexColor("#334155"))
    lines = [
        "1. Tô kín 4 chữ số cuối Mã HS (ví dụ HS0012 -> 0012).",
        "2. Tô kín 3 chữ số Mã đề in ở góc đề giấy (ví dụ 101).",
        f"3. Chỉ tô tối đa 1 đáp án mỗi câu (từ Câu 1 đến Câu {capped_q}).",
        "4. Giữ phẳng phiếu, không gấp hoặc che 4 ô vuông đen ở 4 góc.",
        f"Mã đề gợi ý: {sample_version_code}" if sample_version_code else "Quét/chụp ảnh rõ nét đủ 4 góc đen.",
    ]
    for i, ln in enumerate(lines):
        c.drawString(inst_x1 + 8, inst_y2 - 36 - i * 15, ln)

    # SBD header label & bubbles
    sbd_lbl_x, sbd_lbl_y = uv_to_pdf_pt(SBD_COL_US[0] - 0.015, 0.145)
    c.setFont(bold_font, 9.5)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(sbd_lbl_x, sbd_lbl_y, "MÃ HS (4 SỐ CUỐI)")

    # Mã đề header label
    ver_lbl_x, ver_lbl_y = uv_to_pdf_pt(VERSION_COL_US[0] - 0.01, 0.145)
    c.drawString(ver_lbl_x, ver_lbl_y, "MÃ ĐỀ (3 SỐ)")

    # Draw digit bubbles cleanly
    c.setLineWidth(0.9)
    for target in iter_sbd_bubbles() + iter_version_bubbles():
        bx, by = uv_to_pdf_pt(target.u, target.v)
        c.setStrokeColor(colors.HexColor("#334155"))
        c.setFillColor(colors.white)
        c.circle(bx, by, BUBBLE_RADIUS_PT, stroke=1, fill=1)
        c.setFont(regular_font, 7.2)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawCentredString(bx, by - 2.5, target.value)

    # Column labels for Answers
    for col_us in (ANS_COL1_OPTION_US, ANS_COL2_OPTION_US):
        for lbl, u in zip(ANS_LABELS, col_us, strict=True):
            hx, hy = uv_to_pdf_pt(u, ANS_START_V - 0.025)
            c.setFont(bold_font, 9)
            c.setFillColor(colors.HexColor("#0F172A"))
            c.drawCentredString(hx, hy, lbl)

    for q_num in range(1, capped_q + 1):
        if q_num <= 20:
            row = q_num - 1
            num_u = 0.085
        else:
            row = q_num - 21
            num_u = 0.565
        v = ANS_START_V + row * ANS_STEP_V
        nx, ny = uv_to_pdf_pt(num_u, v)
        c.setFont(bold_font, 8.8)
        c.setFillColor(colors.HexColor("#0F172A"))
        c.drawRightString(nx + 12, ny - 3, f"{q_num}.")

    for target in iter_answer_bubbles(capped_q):
        bx, by = uv_to_pdf_pt(target.u, target.v)
        c.setStrokeColor(colors.HexColor("#334155"))
        c.setFillColor(colors.white)
        c.circle(bx, by, BUBBLE_RADIUS_PT, stroke=1, fill=1)
        c.setFont(regular_font, 7.2)
        c.setFillColor(colors.HexColor("#475569"))
        c.drawCentredString(bx, by - 2.5, target.value)

    c.save()
    return buf.getvalue()


def render_omr_template_png(
    *,
    exam_title: str,
    classroom_name: str,
    question_count: int,
    filled_sbd: str = "",
    filled_version: str = "",
    filled_answers: dict[int, list[str]] | None = None,
    faint_answers: set[int] | None = None,
) -> bytes:
    """Render canonical 1200x1700 OMR sheet PNG (used for offline template & deterministic OMR fixtures)."""
    capped_q = min(max(1, question_count), MAX_OMR_QUESTIONS)
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_bold = load_offline_pil_font(22, bold=True)
    font_reg = load_offline_pil_font(16, bold=False)
    font_small = load_offline_pil_font(12, bold=False)

    # 4 corner solid black fiducial squares
    half_fid = CANVAS_FID_SIZE / 2.0
    for fx, fy in CANVAS_FID_CORNERS:
        draw.rectangle([fx - half_fid, fy - half_fid, fx + half_fid, fy + half_fid], fill=(10, 10, 10))

    tx, ty = uv_to_canvas_px(0.04, 0.025)
    draw.text((tx, ty), f"PHIẾU OMR — {exam_title}", fill=(15, 23, 42), font=font_bold)
    sx, sy = uv_to_canvas_px(0.04, 0.06)
    draw.text((sx, sy), f"Lớp: {classroom_name} | Số câu: {capped_q}", fill=(71, 85, 105), font=font_reg)

    sbd_pad = filled_sbd[-4:].rjust(4, "0") if filled_sbd else ""
    ver_pad = filled_version[-3:].rjust(3, "0") if filled_version else ""

    for target in iter_sbd_bubbles():
        bx, by = uv_to_canvas_px(target.u, target.v)
        r = BUBBLE_RADIUS_PX
        is_filled = bool(sbd_pad and sbd_pad[target.index] == target.value)
        fill_col = (25, 25, 25) if is_filled else (255, 255, 255)
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=fill_col, outline=(60, 60, 60), width=2)
        if not is_filled:
            draw.text((bx - 4, by - 7), target.value, fill=(90, 90, 90), font=font_small)

    for target in iter_version_bubbles():
        bx, by = uv_to_canvas_px(target.u, target.v)
        r = BUBBLE_RADIUS_PX
        is_filled = bool(ver_pad and ver_pad[target.index] == target.value)
        fill_col = (25, 25, 25) if is_filled else (255, 255, 255)
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=fill_col, outline=(60, 60, 60), width=2)
        if not is_filled:
            draw.text((bx - 4, by - 7), target.value, fill=(90, 90, 90), font=font_small)

    for q_num in range(1, capped_q + 1):
        row = q_num - 1 if q_num <= 20 else q_num - 21
        num_u = 0.085 if q_num <= 20 else 0.565
        nx, ny = uv_to_canvas_px(num_u, ANS_START_V + row * ANS_STEP_V)
        draw.text((nx - 14, ny - 9), f"{q_num}.", fill=(15, 23, 42), font=font_reg)

    for target in iter_answer_bubbles(capped_q):
        bx, by = uv_to_canvas_px(target.u, target.v)
        r = BUBBLE_RADIUS_PX
        selected = (filled_answers or {}).get(target.index, [])
        is_filled = target.value in selected
        is_faint = is_filled and bool(faint_answers and target.index in faint_answers)
        fill_col = (210, 210, 210) if is_faint else ((22, 22, 22) if is_filled else (255, 255, 255))
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=fill_col, outline=(60, 60, 60), width=2)
        if not is_filled:
            draw.text((bx - 4, by - 7), target.value, fill=(90, 90, 90), font=font_small)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
