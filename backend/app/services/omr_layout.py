"""Single source of truth A4 geometry & fiducial UV coordinates for ExamGuard OMR sheets."""

from __future__ import annotations

from dataclasses import dataclass

# Standard ISO A4 in PDF points (72 pt/inch)
A4_WIDTH_PT = 595.2756
A4_HEIGHT_PT = 841.8898

# 4 Corner Fiducial square centers in ReportLab PDF points (origin = bottom-left)
FID_MARGIN_PT = 34.0
FID_SIZE_PT = 18.0
FID_LEFT_X = FID_MARGIN_PT
FID_RIGHT_X = A4_WIDTH_PT - FID_MARGIN_PT
FID_TOP_Y = A4_HEIGHT_PT - FID_MARGIN_PT
FID_BOTTOM_Y = FID_MARGIN_PT

ACTIVE_W_PT = FID_RIGHT_X - FID_LEFT_X
ACTIVE_H_PT = FID_TOP_Y - FID_BOTTOM_Y

# Rectified canonical pixel canvas used by OMR scanner & template PNG renderer
CANVAS_W = 1200
CANVAS_H = 1700
CANVAS_FID_MARGIN = 70.0
CANVAS_FID_SIZE = 36.0
CANVAS_ACTIVE_W = CANVAS_W - 2.0 * CANVAS_FID_MARGIN  # 1060.0
CANVAS_ACTIVE_H = CANVAS_H - 2.0 * CANVAS_FID_MARGIN  # 1560.0

CANVAS_FID_CORNERS: tuple[tuple[float, float], ...] = (
    (CANVAS_FID_MARGIN, CANVAS_FID_MARGIN),  # TL
    (CANVAS_W - CANVAS_FID_MARGIN, CANVAS_FID_MARGIN),  # TR
    (CANVAS_FID_MARGIN, CANVAS_H - CANVAS_FID_MARGIN),  # BL
    (CANVAS_W - CANVAS_FID_MARGIN, CANVAS_H - CANVAS_FID_MARGIN),  # BR
)

# Bubble visual radius
BUBBLE_RADIUS_PT = 6.2
BUBBLE_RADIUS_PX = 12.5

# Normalized UV coordinates (u in [0..1] left->right, v in [0..1] top->bottom)
HEADER_ROW_START_V = 0.175
HEADER_ROW_STEP_V = 0.0245

# SBD (4 numeric digits 0..9) columns
SBD_COL_US: tuple[float, ...] = (0.50, 0.55, 0.60, 0.65)
# Mã đề (3 numeric digits 0..9) columns
VERSION_COL_US: tuple[float, ...] = (0.77, 0.82, 0.87)

# Answer bubble grid: up to 40 questions in 2 columns of 20
MAX_OMR_QUESTIONS = 40
ANS_START_V = 0.460
ANS_STEP_V = 0.0255
ANS_COL1_OPTION_US: tuple[float, ...] = (0.165, 0.235, 0.305, 0.375)
ANS_COL2_OPTION_US: tuple[float, ...] = (0.645, 0.715, 0.785, 0.855)
ANS_LABELS: tuple[str, ...] = ("A", "B", "C", "D")


@dataclass(frozen=True)
class BubbleTarget:
    group: str  # "sbd" | "version" | "answer"
    index: int  # column index for header or 1-based question number
    value: str  # "0".."9" or "A".."D"
    u: float
    v: float


def uv_to_pdf_pt(u: float, v: float) -> tuple[float, float]:
    """Convert normalized fiducial UV (top-left origin) to ReportLab bottom-left PDF points."""
    x = FID_LEFT_X + u * ACTIVE_W_PT
    y = FID_TOP_Y - v * ACTIVE_H_PT
    return x, y


def uv_to_canvas_px(u: float, v: float) -> tuple[float, float]:
    """Convert normalized fiducial UV (top-left origin) to canonical 1200x1700 canvas pixels."""
    x = CANVAS_FID_MARGIN + u * CANVAS_ACTIVE_W
    y = CANVAS_FID_MARGIN + v * CANVAS_ACTIVE_H
    return x, y


def iter_sbd_bubbles() -> list[BubbleTarget]:
    targets: list[BubbleTarget] = []
    for col_idx, u in enumerate(SBD_COL_US):
        for digit in range(10):
            v = HEADER_ROW_START_V + digit * HEADER_ROW_STEP_V
            targets.append(BubbleTarget(group="sbd", index=col_idx, value=str(digit), u=u, v=v))
    return targets


def iter_version_bubbles() -> list[BubbleTarget]:
    targets: list[BubbleTarget] = []
    for col_idx, u in enumerate(VERSION_COL_US):
        for digit in range(10):
            v = HEADER_ROW_START_V + digit * HEADER_ROW_STEP_V
            targets.append(BubbleTarget(group="version", index=col_idx, value=str(digit), u=u, v=v))
    return targets


def iter_answer_bubbles(question_count: int = MAX_OMR_QUESTIONS) -> list[BubbleTarget]:
    capped = min(max(1, question_count), MAX_OMR_QUESTIONS)
    targets: list[BubbleTarget] = []
    for q_num in range(1, capped + 1):
        if q_num <= 20:
            row = q_num - 1
            opt_us = ANS_COL1_OPTION_US
        else:
            row = q_num - 21
            opt_us = ANS_COL2_OPTION_US
        v = ANS_START_V + row * ANS_STEP_V
        for lbl, u in zip(ANS_LABELS, opt_us, strict=True):
            targets.append(BubbleTarget(group="answer", index=q_num, value=lbl, u=u, v=v))
    return targets
