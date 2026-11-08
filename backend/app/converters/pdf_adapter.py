"""Pure-Python offline PDF adapter (pypdf BSD): 2-column reading order, raster & vector/OCR guards."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdf
from app.converters.docx_adapter import (
    ContentBlock,
    ExtractedElement,
    ExtractedParagraph,
)
from app.converters.ingest import store_media_asset
from fastapi import HTTPException
from sqlalchemy.orm import Session

# Regex matching PDF vector drawing operators in uncompressed page content streams
_VECTOR_DRAW_RE = re.compile(rb"(?:^|[\s\r\n])(?:-?\d+(?:\.\d+)?\s+){2,}(?:re|m|l|c)(?:$|[\s\r\n])")
_INLINE_QUESTION_START_RE = re.compile(r"^\s*(?:Câu|Question|Bài)\s*\d+\b", re.IGNORECASE)


@dataclass
class _TextSpan:
    x: float
    y: float
    text: str


@dataclass
class _GroupedLine:
    x_min: float
    y: float
    text: str


def _matrix_transform(cm: list[float], tm: list[float]) -> tuple[float, float]:
    """Compute PDF user-space (x, y) from transformation matrices cm and tm."""
    tx = float(tm[4])
    ty = float(tm[5])
    x = float(cm[0]) * tx + float(cm[2]) * ty + float(cm[4])
    y = float(cm[1]) * tx + float(cm[3]) * ty + float(cm[5])
    return x, y


def _group_spans_to_lines(spans: list[_TextSpan], y_tol: float = 3.5) -> list[_GroupedLine]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (-round(s.y, 1), s.x))
    rows: list[list[_TextSpan]] = []
    for sp in ordered:
        clean = sp.text.replace("\r", "").replace("\n", " ")
        if not clean.strip():
            continue
        if not rows or abs(rows[-1][0].y - sp.y) > y_tol:
            rows.append([_TextSpan(x=sp.x, y=sp.y, text=clean)])
        else:
            rows[-1].append(_TextSpan(x=sp.x, y=sp.y, text=clean))

    lines: list[_GroupedLine] = []
    for row in rows:
        row.sort(key=lambda s: s.x)
        joined = ""
        prev_x_end: float | None = None
        for item in row:
            piece = item.text.strip()
            if not piece:
                continue
            if prev_x_end is not None:
                gap = item.x - prev_x_end
                joined += "   " if gap > 22.0 else " "
            joined += piece
            # Approximate span width (~5.2pt per glyph) for inline option gap detection
            prev_x_end = item.x + len(piece) * 5.2
        if joined.strip():
            lines.append(_GroupedLine(x_min=row[0].x, y=row[0].y, text=joined.strip()))
    return lines


def _order_page_lines_reading_order(spans: list[_TextSpan], page_width: float) -> tuple[list[str], bool]:
    """Order text spans into reading lines, handling 2-column layouts cleanly."""
    if not spans:
        return [], False

    # First check raw span positions to see if left/right columns coexist vertically
    mid_x = page_width * 0.48
    left_spans = [s for s in spans if s.x < mid_x and s.text.strip()]
    right_spans = [s for s in spans if s.x >= mid_x and s.text.strip()]

    if len(left_spans) >= 3 and len(right_spans) >= 3:
        # Cluster x_starts of right spans to verify a consistent column margin (e.g. Câu N in col 2)
        right_lines = _group_spans_to_lines(right_spans)
        left_lines = _group_spans_to_lines(left_spans)
        # Verify vertical overlap between left and right columns
        left_ys = [ln.y for ln in left_lines]
        right_ys = [ln.y for ln in right_lines]
        vertical_overlap = (
            min(max(left_ys), max(right_ys)) - max(min(left_ys), min(right_ys))
        ) > 40.0
        # Ensure right column contains independent lines/questions rather than single inline option text
        right_has_question_or_multiline_margin = sum(
            1 for ln in right_lines if _INLINE_QUESTION_START_RE.match(ln.text)
        ) >= 1 or (
            len(right_lines) >= 4
            and max(ln.x_min for ln in left_lines) < mid_x
        )
        # Ensure inline options ("A. x  B. y  C. z  D. w") on same y aren't misread as 2 columns
        if (
            vertical_overlap
            and right_has_question_or_multiline_margin
            and len(left_lines) >= 3
            and len(right_lines) >= 3
        ):
            # Verify left & right columns share vertical bands independently
            single_col_inline_count = sum(
                1
                for ly in left_ys
                if any(abs(ly - ry) <= 3.5 for ry in right_ys)
            )
            if single_col_inline_count >= 1:
                ordered_left = sorted(left_lines, key=lambda ln: -ln.y)
                ordered_right = sorted(right_lines, key=lambda ln: -ln.y)
                return [ln.text for ln in ordered_left] + [ln.text for ln in ordered_right], True

    single_lines = _group_spans_to_lines(spans)
    return [ln.text for ln in sorted(single_lines, key=lambda ln: -ln.y)], False


def _has_vector_diagrams(page: pypdf.PageObject) -> bool:
    try:
        raw_bytes = page._get_contents_as_bytes()  # noqa: SLF001
    except Exception:
        return False
    if not raw_bytes:
        return False
    matches = _VECTOR_DRAW_RE.findall(raw_bytes)
    # A couple lines could be headers/underlines; > 8 vector drawing primitives likely signals geometry/charts
    return len(matches) > 8


def extract_pdf_elements(
    content: bytes,
    *,
    db: Session,
    assets_dir: Path,
) -> tuple[list[ExtractedElement], dict[str, Any]]:
    """Extract ordered ExtractedElements and diagnostics metadata from PDF bytes."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Tệp PDF bị hỏng hoặc không thể đọc.") from exc

    if reader.is_encrypted:
        try:
            res = reader.decrypt("")
            if not res:
                raise HTTPException(
                    status_code=400,
                    detail="Tệp PDF đang khóa mật khẩu; vui lòng bỏ mật khẩu trước khi nhập.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Tệp PDF được bảo vệ mật khẩu; không thể trích xuất.",
            ) from exc

    if len(reader.pages) == 0:
        raise HTTPException(status_code=400, detail="Tệp PDF không có trang nào.")

    elements: list[ExtractedElement] = []
    elem_idx = 0
    two_col_pages: list[int] = []
    vector_pages: list[int] = []
    low_text_pages: list[int] = []
    extracted_image_count = 0

    for page_num, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        page_width = float(box.width) if box and float(box.width) > 0 else 595.0

        spans: list[_TextSpan] = []

        def _make_visitor(target_spans: list[_TextSpan]) -> Any:
            def _visitor(text: Any, cm: Any, tm: Any, _fd: Any, _fs: Any) -> None:
                txt = str(text or "")
                if not txt.strip():
                    return
                x, y = _matrix_transform(list(cm), list(tm))
                target_spans.append(_TextSpan(x=x, y=y, text=txt))

            return _visitor

        try:
            page.extract_text(visitor_text=_make_visitor(spans))
        except Exception:
            fallback_txt = page.extract_text() or ""
            for line_i, ln in enumerate(fallback_txt.splitlines()):
                if ln.strip():
                    spans.append(_TextSpan(x=50.0, y=800.0 - line_i * 14.0, text=ln))

        ordered_lines, is_two_col = _order_page_lines_reading_order(spans, page_width)
        if is_two_col:
            two_col_pages.append(page_num)

        has_vector = _has_vector_diagrams(page)
        if has_vector:
            vector_pages.append(page_num)

        total_chars = sum(len(ln) for ln in ordered_lines)
        page_images: list[ContentBlock] = []
        try:
            for img_i, img in enumerate(page.images, start=1):
                data = getattr(img, "data", b"")
                name = getattr(img, "name", f"pdf_p{page_num}_img{img_i}.png")
                if not data:
                    continue
                asset = store_media_asset(
                    db,
                    assets_dir=assets_dir,
                    filename=str(name),
                    content=bytes(data),
                )
                extracted_image_count += 1
                page_images.append(
                    ContentBlock(
                        type="image",
                        data={
                            "asset_id": asset.id,
                            "alt": f"Hình trích từ PDF trang {page_num}",
                            "source_anchor": f"page={page_num}:img={img_i}",
                        },
                    )
                )
        except Exception:
            page_images = []

        page_warnings: list[str] = []
        if has_vector:
            page_warnings.append("PDF_VECTOR_OR_COMPLEX_LAYOUT")
        if total_chars < 35 and (page_images or page_num >= 1):
            low_text_pages.append(page_num)
            page_warnings.append("PDF_LOW_TEXT_DENSITY_OCR_NEEDED")

        for ln in ordered_lines:
            elem_idx += 1
            elements.append(
                ExtractedElement(
                    kind="paragraph",
                    paragraph=ExtractedParagraph(
                        index=elem_idx,
                        source_anchor=f"pdf:page={page_num}",
                        blocks=[ContentBlock(type="text", data={"text": ln})],
                        plain_text=ln,
                        warnings=list(page_warnings),
                    ),
                )
            )

        # Attach extracted raster images from this page into element stream so reviewer can see/re-place them
        for img_block in page_images:
            elem_idx += 1
            elements.append(
                ExtractedElement(
                    kind="paragraph",
                    paragraph=ExtractedParagraph(
                        index=elem_idx,
                        source_anchor=f"pdf:page={page_num}:media",
                        blocks=[img_block],
                        plain_text="",
                        warnings=list(page_warnings),
                    ),
                )
            )

    diagnostics = {
        "page_count": len(reader.pages),
        "two_column_pages": two_col_pages,
        "vector_diagram_pages": vector_pages,
        "low_text_pages": low_text_pages,
        "extracted_images": extracted_image_count,
    }
    return elements, diagnostics
