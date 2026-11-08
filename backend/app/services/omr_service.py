"""Offline OMR perspective rectification, bubble fill scoring, teacher review queue, and shared score bridge."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from app.core.config import Settings
from app.db.locks import EXAM_WRITE_LOCK
from app.db.models import (
    Attempt,
    ClassMembership,
    Exam,
    ExamQuestion,
    GradeRun,
    OmrScanSubmission,
    PaperVersion,
    Student,
    Submission,
)
from app.services.audit_service import record_audit_event
from app.services.grading_service import run_grading_for_exam
from app.services.omr_layout import (
    ANS_LABELS,
    BUBBLE_RADIUS_PX,
    CANVAS_FID_CORNERS,
    CANVAS_H,
    CANVAS_W,
    MAX_OMR_QUESTIONS,
    iter_answer_bubbles,
    iter_sbd_bubbles,
    iter_version_bubbles,
    uv_to_canvas_px,
)
from fastapi import HTTPException, status
from PIL import Image, ImageDraw
from sqlalchemy import func, select
from sqlalchemy.orm import Session

MAX_SCAN_BYTES = 20 * 1024 * 1024
ALLOWED_SCAN_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# Precompute integer sampling offsets for inner bubble circle vs surrounding white ring
_SAMPLE_GRID_R = 23
_DY, _DX = np.ogrid[-_SAMPLE_GRID_R : _SAMPLE_GRID_R + 1, -_SAMPLE_GRID_R : _SAMPLE_GRID_R + 1]
_DIST2 = _DX * _DX + _DY * _DY
_INNER_MASK = _DIST2 <= 81  # r <= 9 px (inside BUBBLE_RADIUS_PX=12.5)
_RING_MASK = (_DIST2 >= 225) & (_DIST2 <= 441)  # 15 <= r <= 21 px (clear white margin)
_INNER_DY, _INNER_DX = np.where(_INNER_MASK)
_INNER_DY = _INNER_DY - _SAMPLE_GRID_R
_INNER_DX = _INNER_DX - _SAMPLE_GRID_R
_RING_DY, _RING_DX = np.where(_RING_MASK)
_RING_DY = _RING_DY - _SAMPLE_GRID_R
_RING_DX = _RING_DX - _SAMPLE_GRID_R


@dataclass(frozen=True)
class BubbleRead:
    label: str
    mean_contrast: float
    coverage25: float
    cx: float
    cy: float


def _validate_image_bytes(filename: str, content: bytes) -> tuple[Image.Image, str]:
    if not content:
        raise HTTPException(status_code=400, detail="Tệp ảnh phiếu OMR trống.")
    if len(content) > MAX_SCAN_BYTES:
        raise HTTPException(status_code=400, detail="Tệp ảnh phiếu OMR vượt quá 20 MB.")

    ext = Path(filename or "scan.png").suffix.lower()
    if ext not in ALLOWED_SCAN_EXTS:
        ext = ".png"

    prev_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 40_000_000
    try:
        with Image.open(io.BytesIO(content)) as opened:
            opened.load()
            rgb = opened.convert("RGB")
            return rgb, ext
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=400,
            detail="Ảnh phiếu OMR có kích thước điểm ảnh vượt ngưỡng an toàn.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Không thể đọc định dạng ảnh phiếu OMR.") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = prev_max


def _find_corner_fiducial(
    gray_small: np.ndarray,
    *,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    anchor_x: float,
    anchor_y: float,
    page_area: int,
) -> tuple[float, float] | None:
    roi = gray_small[y0:y1, x0:x1]
    if roi.size < 64:
        return None
    bg = float(np.percentile(roi, 85))
    mn = float(np.min(roi))
    if bg - mn < 45.0:
        return None

    thresh = mn + 0.42 * (bg - mn)
    mask = roi < thresh
    h_r, w_r = mask.shape
    visited = np.zeros_like(mask, dtype=np.bool_)

    min_area = max(14, int(0.00018 * page_area))
    max_area = max(min_area + 20, int(0.03 * page_area))

    best_score = -1.0
    best_centroid: tuple[float, float] | None = None

    ys_dark, xs_dark = np.where(mask)
    for sy_raw, sx_raw in zip(ys_dark.tolist(), xs_dark.tolist(), strict=True):
        if visited[sy_raw, sx_raw]:
            continue
        q: deque[tuple[int, int]] = deque([(sy_raw, sx_raw)])
        visited[sy_raw, sx_raw] = True
        pixels_x: list[int] = []
        pixels_y: list[int] = []
        min_x = max_x = sx_raw
        min_y = max_y = sy_raw

        while q:
            cy, cx = q.popleft()
            pixels_x.append(cx)
            pixels_y.append(cy)
            if cx < min_x:
                min_x = cx
            if cx > max_x:
                max_x = cx
            if cy < min_y:
                min_y = cy
            if cy > max_y:
                max_y = cy

            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h_r and 0 <= nx < w_r and not visited[ny, nx] and mask[ny, nx]:
                    visited[ny, nx] = True
                    q.append((ny, nx))

        area = len(pixels_x)
        if area < min_area or area > max_area:
            continue
        bw = max_x - min_x + 1
        bh = max_y - min_y + 1
        aspect = bw / max(bh, 1)
        solidity = area / max(bw * bh, 1)
        if not (0.55 <= aspect <= 1.80) or solidity < 0.62:
            continue

        cx_global = x0 + float(sum(pixels_x)) / area
        cy_global = y0 + float(sum(pixels_y)) / area

        # Prefer high solidity and close proximity to outer page corner
        dist_norm = ((cx_global - anchor_x) ** 2 + (cy_global - anchor_y) ** 2) ** 0.5 / max(
            (gray_small.shape[1] ** 2 + gray_small.shape[0] ** 2) ** 0.5, 1.0
        )
        score = solidity * 2.0 - abs(1.0 - aspect) * 0.5 - dist_norm * 1.5
        if score > best_score:
            best_score = score
            best_centroid = (cx_global, cy_global)

    return best_centroid


def _detect_four_fiducials(rgb_img: Image.Image) -> list[tuple[float, float]] | None:
    """Locate (TL, TR, BL, BR) corner fiducial centroids in full-res RGB image."""
    orig_w, orig_h = rgb_img.size
    scale = min(1.0, 600.0 / max(orig_w, 1))
    sw = max(120, int(round(orig_w * scale)))
    sh = max(160, int(round(orig_h * scale)))

    gray = np.asarray(
        rgb_img.resize((sw, sh), Image.Resampling.BILINEAR).convert("L"),
        dtype=np.float32,
    )
    page_area = sw * sh

    # Outer quadrant windows (generous overlap to handle tilt/rotation up to ~20 deg)
    tl = _find_corner_fiducial(
        gray, x0=0, x1=int(sw * 0.35), y0=0, y1=int(sh * 0.30),
        anchor_x=0.0, anchor_y=0.0, page_area=page_area,
    )
    tr = _find_corner_fiducial(
        gray, x0=int(sw * 0.65), x1=sw, y0=0, y1=int(sh * 0.30),
        anchor_x=float(sw), anchor_y=0.0, page_area=page_area,
    )
    bl = _find_corner_fiducial(
        gray, x0=0, x1=int(sw * 0.35), y0=int(sh * 0.70), y1=sh,
        anchor_x=0.0, anchor_y=float(sh), page_area=page_area,
    )
    br = _find_corner_fiducial(
        gray, x0=int(sw * 0.65), x1=sw, y0=int(sh * 0.70), y1=sh,
        anchor_x=float(sw), anchor_y=float(sh), page_area=page_area,
    )

    if tl is None or tr is None or bl is None or br is None:
        return None

    inv_x = orig_w / sw
    inv_y = orig_h / sh
    pts = [
        (tl[0] * inv_x, tl[1] * inv_y),
        (tr[0] * inv_x, tr[1] * inv_y),
        (bl[0] * inv_x, bl[1] * inv_y),
        (br[0] * inv_x, br[1] * inv_y),
    ]
    # Geometric quadrilateral sanity check
    top_w = pts[1][0] - pts[0][0]
    bot_w = pts[3][0] - pts[2][0]
    left_h = pts[2][1] - pts[0][1]
    right_h = pts[3][1] - pts[1][1]
    if min(top_w, bot_w) < 0.35 * orig_w or min(left_h, right_h) < 0.40 * orig_h:
        return None
    return pts


def _solve_perspective_coeffs(
    dst_pts: tuple[tuple[float, float], ...],
    src_pts: list[tuple[float, float]],
) -> tuple[float, ...]:
    """Compute 8 projective transform coeffs mapping canonical dst (x, y) -> input src (X, Y)."""
    matrix: list[list[float]] = []
    rhs: list[float] = []
    for (x, y), (src_x, src_y) in zip(dst_pts, src_pts, strict=True):
        matrix.append([x, y, 1.0, 0.0, 0.0, 0.0, -src_x * x, -src_x * y])
        rhs.append(src_x)
        matrix.append([0.0, 0.0, 0.0, x, y, 1.0, -src_y * x, -src_y * y])
        rhs.append(src_y)
    sol = np.linalg.solve(np.array(matrix, dtype=np.float64), np.array(rhs, dtype=np.float64))
    return tuple(float(v) for v in sol.tolist())


def _sample_bubble(gray_canvas: np.ndarray, cx: float, cy: float, label: str) -> BubbleRead:
    h, w = gray_canvas.shape
    ix = int(round(cx))
    iy = int(round(cy))
    if (
        ix < _SAMPLE_GRID_R + 1
        or ix >= w - _SAMPLE_GRID_R - 1
        or iy < _SAMPLE_GRID_R + 1
        or iy >= h - _SAMPLE_GRID_R - 1
    ):
        return BubbleRead(label=label, mean_contrast=0.0, coverage25=0.0, cx=cx, cy=cy)

    inner_vals = gray_canvas[iy + _INNER_DY, ix + _INNER_DX]
    ring_vals = gray_canvas[iy + _RING_DY, ix + _RING_DX]
    ring_bg = max(float(np.percentile(ring_vals, 75)), 45.0)
    local_dark = np.clip((ring_bg - inner_vals) / ring_bg, 0.0, 1.0)
    mean_c = float(np.mean(local_dark))
    cov25 = float(np.mean(local_dark >= 0.25))
    return BubbleRead(label=label, mean_contrast=mean_c, coverage25=cov25, cx=cx, cy=cy)


def _classify_column_digits(reads: list[BubbleRead]) -> tuple[str | None, float, str]:
    ordered = sorted(reads, key=lambda r: r.mean_contrast, reverse=True)
    top = ordered[0]
    second = ordered[1]
    if top.mean_contrast < 0.14:
        return None, 0.0, "BLANK"
    if second.mean_contrast >= 0.20 and (top.mean_contrast - second.mean_contrast) < 0.14:
        return top.label, 0.35, "AMBIGUOUS"
    if top.mean_contrast < 0.30 or top.coverage25 < 0.50:
        return top.label, round(min(0.65, top.mean_contrast + 0.25), 3), "FAINT"
    conf = min(0.99, 0.72 + 0.45 * (top.mean_contrast - second.mean_contrast))
    return top.label, round(conf, 3), "CONFIDENT"


def _classify_question_bubbles(reads: list[BubbleRead]) -> tuple[str | None, float, str]:
    ordered = sorted(reads, key=lambda r: r.mean_contrast, reverse=True)
    top = ordered[0]
    second = ordered[1]
    if top.mean_contrast < 0.13:
        # Check slightly faint trace vs truly blank
        status_str = "FAINT" if top.mean_contrast >= 0.085 else "BLANK"
        return None, round(1.0 - top.mean_contrast * 2.0, 3) if status_str == "BLANK" else 0.40, status_str
    if second.mean_contrast >= 0.18 and (top.mean_contrast - second.mean_contrast) < 0.13:
        return top.label, 0.30, "AMBIGUOUS"
    if top.mean_contrast < 0.30 or top.coverage25 < 0.50:
        return top.label, round(min(0.68, 0.40 + top.mean_contrast), 3), "FAINT"
    conf = min(0.99, 0.74 + 0.45 * (top.mean_contrast - second.mean_contrast))
    return top.label, round(conf, 3), "CONFIDENT"


def process_and_store_omr_scan(
    db: Session,
    *,
    exam_id: str,
    filename: str,
    content: bytes,
    settings: Settings,
    teacher_id: int,
) -> OmrScanSubmission:
    """Persist immutable original scan, rectify perspective, score bubbles, flag ambiguities."""
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi.")

    exam_qs = (
        db.execute(select(ExamQuestion).where(ExamQuestion.exam_id == exam.id))
        .scalars()
        .all()
    )
    if not exam_qs:
        raise HTTPException(status_code=400, detail="Kỳ thi chưa có câu hỏi để đối chiếu OMR.")
    q_count = min(len(exam_qs), MAX_OMR_QUESTIONS)

    rgb_img, ext = _validate_image_bytes(filename, content)
    sha = hashlib.sha256(content).hexdigest()
    scan_id = str(uuid.uuid4())

    settings.scans_dir.mkdir(parents=True, exist_ok=True)
    source_relpath = f"{scan_id}{ext}"
    source_abs = (settings.scans_dir / source_relpath).resolve()
    if not source_abs.is_relative_to(settings.scans_dir.resolve()):
        raise HTTPException(status_code=400, detail="Đường dẫn lưu scan OMR không hợp lệ.")
    source_abs.write_bytes(content)

    # Rectify image onto canonical 1200x1700 frame
    fid_pts = _detect_four_fiducials(rgb_img)
    ambiguous_flags: list[str] = []

    if fid_pts is not None:
        coeffs = _solve_perspective_coeffs(CANVAS_FID_CORNERS, fid_pts)
        rectified = rgb_img.transform(
            (CANVAS_W, CANVAS_H),
            Image.Transform.PERSPECTIVE,
            coeffs,
            Image.Resampling.BILINEAR,
        )
        fiducial_found = True
    else:
        rectified = rgb_img.resize((CANVAS_W, CANVAS_H), Image.Resampling.BILINEAR)
        fiducial_found = False
        ambiguous_flags.append("FIDUCIAL_NOT_FOUND")

    gray_canvas = np.asarray(rectified.convert("L"), dtype=np.float32)
    preview_img = rectified.copy()
    draw = ImageDraw.Draw(preview_img)

    # Read SBD (4 columns)
    sbd_by_col: dict[int, list[BubbleRead]] = {i: [] for i in range(4)}
    for t in iter_sbd_bubbles():
        px, py = uv_to_canvas_px(t.u, t.v)
        sbd_by_col[t.index].append(_sample_bubble(gray_canvas, px, py, t.value))

    sbd_digits: list[str] = []
    sbd_ambiguous = False
    for col_i in range(4):
        val, _conf, st = _classify_column_digits(sbd_by_col[col_i])
        if val is None or st in {"AMBIGUOUS", "FAINT"}:
            sbd_ambiguous = True
            sbd_digits.append(val or "?")
        else:
            sbd_digits.append(val)
    roster_code_detected = "".join(sbd_digits)

    # Read Mã đề (3 columns)
    ver_by_col: dict[int, list[BubbleRead]] = {i: [] for i in range(3)}
    for t in iter_version_bubbles():
        px, py = uv_to_canvas_px(t.u, t.v)
        ver_by_col[t.index].append(_sample_bubble(gray_canvas, px, py, t.value))

    ver_digits: list[str] = []
    ver_ambiguous = False
    for col_i in range(3):
        val, _conf, st = _classify_column_digits(ver_by_col[col_i])
        if val is None or st in {"AMBIGUOUS", "FAINT"}:
            ver_ambiguous = True
            ver_digits.append(val or "?")
        else:
            ver_digits.append(val)
    version_code_detected = "".join(ver_digits)

    # Read Question Answers 1..q_count
    ans_by_q: dict[int, list[BubbleRead]] = {q: [] for q in range(1, q_count + 1)}
    for t in iter_answer_bubbles(q_count):
        px, py = uv_to_canvas_px(t.u, t.v)
        ans_by_q[t.index].append(_sample_bubble(gray_canvas, px, py, t.value))

    detected_answers: dict[str, str | None] = {}
    conf_details: dict[str, Any] = {
        "fiducial_found": fiducial_found,
        "sbd_digits": sbd_digits,
        "version_digits": ver_digits,
        "questions": {},
    }
    q_confs: list[float] = []

    for q_num in range(1, q_count + 1):
        reads = ans_by_q[q_num]
        sel, q_conf, q_st = _classify_question_bubbles(reads)
        detected_answers[str(q_num)] = sel
        conf_details["questions"][str(q_num)] = {
            "status": q_st,
            "confidence": q_conf,
            "scores": {r.label: round(r.mean_contrast, 3) for r in reads},
        }
        q_confs.append(q_conf if fiducial_found else 0.0)

        # Draw visual review marker over chosen/flagged bubbles
        if q_st in {"AMBIGUOUS", "FAINT"}:
            ambiguous_flags.append(f"Q{q_num}_{q_st}")
        elif q_st == "BLANK" and not fiducial_found:
            ambiguous_flags.append(f"Q{q_num}_FIDUCIAL_MISSING")

        if sel:
            chosen_read = next((r for r in reads if r.label == sel), None)
            if chosen_read is not None:
                box_col = (
                    (22, 163, 74) if (q_st == "CONFIDENT" and fiducial_found) else (217, 119, 6)
                )
                r_px = BUBBLE_RADIUS_PX + 4
                draw.rectangle(
                    [
                        chosen_read.cx - r_px,
                        chosen_read.cy - r_px,
                        chosen_read.cx + r_px,
                        chosen_read.cy + r_px,
                    ],
                    outline=box_col,
                    width=3,
                )

    # Match roster_code_detected to Student in classroom
    matched_student: Student | None = None
    if "?" not in roster_code_detected and not sbd_ambiguous:
        students = (
            db.execute(
                select(Student)
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
        candidates = [
            st
            for st in students
            if "".join(ch for ch in st.roster_code if ch.isdigit())[-4:].rjust(4, "0")
            == roster_code_detected
        ]
        if len(candidates) == 1:
            matched_student = candidates[0]
        else:
            ambiguous_flags.append("HEADER_STUDENT_NOT_UNIQUE")
    else:
        ambiguous_flags.append("HEADER_STUDENT_AMBIGUOUS")

    # Match version_code_detected to PaperVersion for this exam
    matched_pv: PaperVersion | None = None
    if "?" not in version_code_detected and not ver_ambiguous:
        matched_pv = db.execute(
            select(PaperVersion).where(
                PaperVersion.exam_id == exam.id,
                PaperVersion.version_code == version_code_detected,
            )
        ).scalar_one_or_none()
        if matched_pv is None:
            ambiguous_flags.append("HEADER_VERSION_NOT_FOUND")
    else:
        ambiguous_flags.append("HEADER_VERSION_AMBIGUOUS")

    aligned_relpath = f"aligned_{scan_id}.png"
    aligned_abs = (settings.scans_dir / aligned_relpath).resolve()
    preview_img.save(aligned_abs, format="PNG")

    overall_conf = round(sum(q_confs) / max(len(q_confs), 1), 3) if fiducial_found else 0.0
    # Strict safety: always keep newly ingested OMR scans in NEEDS_REVIEW until teacher confirmation
    # (or at minimum flag any ambiguity visibly in teacher queue).
    scan = OmrScanSubmission(
        id=scan_id,
        exam_id=exam.id,
        student_id=matched_student.id if matched_student else None,
        paper_version_id=matched_pv.id if matched_pv else None,
        roster_code_detected=roster_code_detected,
        version_code_detected=version_code_detected,
        source_image_relpath=source_relpath,
        source_sha256=sha,
        aligned_preview_relpath=aligned_relpath,
        detected_answers_json=json.dumps(detected_answers, ensure_ascii=False),
        confirmed_answers_json=json.dumps(detected_answers, ensure_ascii=False),
        confidence_json=json.dumps(conf_details, ensure_ascii=False),
        ambiguous_questions_json=json.dumps(list(dict.fromkeys(ambiguous_flags)), ensure_ascii=False),
        overall_confidence=overall_conf,
        status="NEEDS_REVIEW",
    )
    db.add(scan)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="UPLOAD_OMR_SCAN",
        target_type="omr_scan",
        target_id=scan.id,
        details={
            "exam_id": exam.id,
            "source_sha256": sha,
            "fiducial_found": fiducial_found,
            "overall_confidence": overall_conf,
            "ambiguous_flags": ambiguous_flags,
        },
    )
    db.commit()
    db.refresh(scan)
    return scan


def confirm_omr_scan(
    db: Session,
    *,
    scan_id: str,
    student_id: str,
    version_code: str,
    confirmed_answers: dict[str, str | None],
    reason: str,
    teacher_id: int,
    settings: Settings,
) -> tuple[OmrScanSubmission, str, bool]:
    """Verify teacher OMR review, create immutable paper Submission, and bridge to shared grading."""
    clean_reason = reason.strip() or "Giáo viên xác nhận phiếu tô OMR"
    scan = db.get(OmrScanSubmission, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu OMR.")

    exam = db.get(Exam, scan.exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy kỳ thi của phiếu OMR.")

    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh được chọn.")

    pv = db.execute(
        select(PaperVersion).where(
            PaperVersion.exam_id == exam.id,
            PaperVersion.version_code == version_code.strip(),
        )
    ).scalar_one_or_none()
    if pv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy Mã đề giấy '{version_code}' trong kỳ thi này.",
        )

    detected: dict[str, str | None] = json.loads(scan.detected_answers_json)
    overrides = [
        q
        for q, v in confirmed_answers.items()
        if (detected.get(q) or None) != (v.upper().strip() if isinstance(v, str) and v.strip() else None)
    ]
    if overrides and len(reason.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Khi điều chỉnh đáp án nhận diện OMR, bắt buộc nhập lý do (>= 3 ký tự).",
        )

    q_order: list[str] = json.loads(pv.question_order_json)
    opt_order: dict[str, list[str]] = json.loads(pv.option_order_json)

    # Translate 1-based printed question number + selected letter ("A".."D") -> canonical option_id
    canonical_answers: dict[str, list[str]] = {}
    clean_confirmed_map: dict[str, str | None] = {}
    for q_idx, qvid in enumerate(q_order, start=1):
        raw_choice = confirmed_answers.get(str(q_idx))
        clean_letter = raw_choice.upper().strip() if isinstance(raw_choice, str) and raw_choice.strip() else None
        if clean_letter is not None and clean_letter not in ANS_LABELS:
            raise HTTPException(
                status_code=400,
                detail=f"Đáp án câu {q_idx} phải thuộc A, B, C, D hoặc để trống.",
            )
        clean_confirmed_map[str(q_idx)] = clean_letter
        ordered_opt_ids = opt_order.get(qvid, [])
        if clean_letter is not None:
            letter_idx = ANS_LABELS.index(clean_letter)
            if letter_idx >= len(ordered_opt_ids):
                raise HTTPException(
                    status_code=400,
                    detail=f"Câu {q_idx} không có phương án '{clean_letter}'.",
                )
            canonical_answers[qvid] = [ordered_opt_ids[letter_idx]]
        else:
            canonical_answers[qvid] = []

    now = datetime.now(UTC)
    regraded = False

    with EXAM_WRITE_LOCK:
        existing_attempt = db.execute(
            select(Attempt).where(Attempt.exam_id == exam.id, Attempt.student_id == student.id)
        ).scalar_one_or_none()
        existing_sub = (
            db.execute(
                select(Submission).where(Submission.exam_id == exam.id, Submission.student_id == student.id)
            ).scalar_one_or_none()
        )
        if (
            existing_sub is not None
            and existing_sub.id != scan.linked_submission_id
            and existing_sub.submission_mode != "paper_omr_confirmed"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Học sinh này đã có bài nộp trực tuyến; không thể ghi đè âm thầm bằng phiếu OMR.",
            )

        if existing_attempt is None:
            existing_attempt = Attempt(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                student_id=student.id,
                session_id=f"paper-omr-{scan.id[:8]}",
                state="SUBMITTED",
                presence_state="PAPER_MODE",
                latest_revision=1,
                started_at=now,
                submitted_at=now,
            )
            db.add(existing_attempt)
            db.flush()
        else:
            existing_attempt.state = "SUBMITTED"
            existing_attempt.presence_state = "PAPER_MODE"
            existing_attempt.submitted_at = existing_attempt.submitted_at or now

        canon_json = json.dumps(canonical_answers, sort_keys=True, ensure_ascii=False)
        snap_hash = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()

        if existing_sub is not None and existing_sub.id == scan.linked_submission_id:
            # Update only if re-confirming the exact linked paper OMR submission
            sub = existing_sub
            sub.answer_snapshot_json = canon_json
            sub.snapshot_hash = snap_hash
        elif existing_sub is None:
            sub = Submission(
                id=str(uuid.uuid4()),
                attempt_id=existing_attempt.id,
                exam_id=exam.id,
                student_id=student.id,
                answer_snapshot_json=canon_json,
                snapshot_hash=snap_hash,
                submission_mode="paper_omr_confirmed",
                submitted_at=now,
            )
            db.add(sub)
            db.flush()
        else:
            # Replace only when existing_sub is also paper_omr_confirmed from a prior scan retry
            sub = existing_sub
            sub.answer_snapshot_json = canon_json
            sub.snapshot_hash = snap_hash
            sub.submitted_at = now

        scan.student_id = student.id
        scan.paper_version_id = pv.id
        scan.confirmed_answers_json = json.dumps(clean_confirmed_map, ensure_ascii=False)
        scan.status = "CONFIRMED"
        scan.linked_attempt_id = existing_attempt.id
        scan.linked_submission_id = sub.id
        scan.confirmed_by = teacher_id
        scan.confirmed_at = now
        scan.reason = clean_reason[:300]

        record_audit_event(
            db,
            actor_type="teacher",
            actor_id=str(teacher_id),
            action="CONFIRM_OMR_SCAN",
            target_type="omr_scan",
            target_id=scan.id,
            details={
                "exam_id": exam.id,
                "student_id": student.id,
                "version_code": pv.version_code,
                "submission_id": sub.id,
                "overrides_count": len(overrides),
                "reason": clean_reason[:300],
            },
        )
        db.commit()

    # Bridge directly into shared GradeRun/ScoreVersion if exam already closed or graded
    existing_runs = int(
        db.execute(select(func.count()).select_from(GradeRun).where(GradeRun.exam_id == exam.id)).scalar_one()
    )
    if existing_runs > 0 or exam.status in {"CLOSED", "REVIEWED", "PUBLISHED"}:
        run_grading_for_exam(
            db,
            exam_id=exam.id,
            teacher_id=teacher_id,
            reason=f"Đồng bộ bài giấy OMR ({student.roster_code} · Mã đề {pv.version_code}): {clean_reason[:120]}",
            settings=settings,
        )
        regraded = True

    db.refresh(scan)
    return scan, sub.id, regraded
