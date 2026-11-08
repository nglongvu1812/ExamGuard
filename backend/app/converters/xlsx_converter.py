"""Rule-based Excel (.xlsx) question converter supporting flexible teacher header/column profiles."""

from __future__ import annotations

import io
import uuid
from typing import Any

import openpyxl
from app.converters.segmenter import SegmentedOption, SegmentedQuestionDraft
from fastapi import HTTPException

SUPPORTED_XLSX_PROFILES = {
    "auto": "Tự động nhận diện tiêu đề cột (Tiếng Việt / Tiếng Anh)",
    "vn_standard": "Mẫu chuẩn Việt Nam (Câu hỏi | A | B | C | D | Đáp án đúng)",
    "english_bank": "Mẫu Quốc tế (Question | Option A..D | Correct Answer)",
    "positional_abcd": "Mẫu theo thứ tự cột cố định (Cột 1/2=Câu hỏi, kế tiếp A..D, cuối=Đáp án)",
}

_STEM_SYNONYMS = {
    "cau hoi",
    "câu hỏi",
    "noi dung",
    "nội dung",
    "noi dung cau hoi",
    "nội dung câu hỏi",
    "question",
    "stem",
    "prompt",
    "de bai",
    "đề bài",
}

_KEY_SYNONYMS = {
    "dap an",
    "đáp án",
    "dap an dung",
    "đáp án đúng",
    "key",
    "correct",
    "correct answer",
    "answer",
    "ket qua",
    "kết quả",
}

_OPT_SYNONYMS: dict[str, set[str]] = {
    "A": {"a", "dap an a", "đáp án a", "option a", "phuong an a", "phương án a", "opt a", "choice a"},
    "B": {"b", "dap an b", "đáp án b", "option b", "phuong an b", "phương án b", "opt b", "choice b"},
    "C": {"c", "dap an c", "đáp án c", "option c", "phuong an c", "phương án c", "opt c", "choice c"},
    "D": {"d", "dap an d", "đáp án d", "option d", "phuong an d", "phương án d", "opt d", "choice d"},
    "E": {"e", "dap an e", "đáp án e", "option e", "phuong an e", "phương án e", "opt e", "choice e"},
}

_INDEX_SYNONYMS = {"stt", "no", "index", "thu tu", "thứ tự", "ma cau", "mã câu"}


def _norm_header(val: Any) -> str:
    raw = str(val or "").strip().lower()
    raw = " ".join(raw.replace("_", " ").replace("-", " ").split())
    return raw


def _cell_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def _detect_header_mapping(
    row_values: list[Any],
    profile: str,
) -> dict[str, Any] | None:
    normed = [_norm_header(v) for v in row_values]
    if not any(normed):
        return None

    stem_col: int | None = None
    key_col: int | None = None
    opt_cols: dict[str, int] = {}

    for idx, hdr in enumerate(normed):
        if not hdr or hdr in _INDEX_SYNONYMS:
            continue
        if profile == "vn_standard" and hdr in {"câu hỏi", "cau hoi", "nội dung", "noi dung"}:
            stem_col = idx
            continue
        if profile == "english_bank" and hdr in {"question", "stem"}:
            stem_col = idx
            continue
        if hdr in _STEM_SYNONYMS and stem_col is None:
            stem_col = idx
            continue
        if hdr in _KEY_SYNONYMS and key_col is None:
            key_col = idx
            continue
        for lbl, syns in _OPT_SYNONYMS.items():
            if hdr in syns and lbl not in opt_cols:
                opt_cols[lbl] = idx
                break

    if stem_col is not None and len(opt_cols) >= 2:
        return {"stem": stem_col, "options": opt_cols, "key": key_col, "has_header": True}
    return None


def _build_positional_mapping(first_row: list[Any]) -> dict[str, Any]:
    """Map positional columns when teacher omits standard headers."""
    start = 0
    if first_row and _cell_str(first_row[0]).isdigit():
        start = 1
    opt_cols = {"A": start + 1, "B": start + 2, "C": start + 3, "D": start + 4}
    key_col = start + 5 if len(first_row) > start + 5 else None
    return {"stem": start, "options": opt_cols, "key": key_col, "has_header": False}


def parse_xlsx_questions(
    content: bytes,
    *,
    profile: str = "auto",
) -> tuple[list[SegmentedQuestionDraft], dict[str, Any]]:
    """Parse teacher Excel question bank into SegmentedQuestionDraft items without guessing missing keys."""
    if profile not in SUPPORTED_XLSX_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Không hỗ trợ profile Excel '{profile}'.",
        )

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Không thể đọc tệp Excel (.xlsx).") from exc

    try:
        ws = wb.active
        if ws is None:
            raise HTTPException(status_code=400, detail="Tệp Excel không có trang tính (sheet) nào.")

        all_rows: list[list[Any]] = []
        for row in ws.iter_rows(values_only=True):
            vals = list(row)
            if any(_cell_str(v) for v in vals):
                all_rows.append(vals)
    finally:
        wb.close()

    if not all_rows:
        raise HTTPException(status_code=400, detail="Trang tính Excel đang trống.")

    mapping: dict[str, Any] | None = None
    data_start_idx = 0
    if profile != "positional_abcd":
        for i in range(min(5, len(all_rows))):
            detected = _detect_header_mapping(all_rows[i], profile)
            if detected is not None:
                mapping = detected
                data_start_idx = i + 1
                break

    if mapping is None:
        if profile in {"vn_standard", "english_bank"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Không tìm thấy cột tiêu đề hợp lệ cho profile '{profile}' "
                    "(cần cột Câu hỏi/Question và ít nhất 2 cột phương án A, B)."
                ),
            )
        # Positional fallback only if not explicitly constrained to header profile
        # Check if first row looks like a header label row
        first_norm = {_norm_header(v) for v in all_rows[0] if _cell_str(v)}
        looks_header = bool(first_norm & (_STEM_SYNONYMS | _INDEX_SYNONYMS))
        if looks_header:
            mapping = _build_positional_mapping(all_rows[1] if len(all_rows) > 1 else all_rows[0])
            data_start_idx = 1
        else:
            mapping = _build_positional_mapping(all_rows[0])
            data_start_idx = 0

    stem_col = int(mapping["stem"])
    opt_cols: dict[str, int] = dict(mapping["options"])
    key_col: int | None = mapping["key"]

    drafts: list[SegmentedQuestionDraft] = []
    for row_offset, row in enumerate(all_rows[data_start_idx:], start=data_start_idx + 1):
        stem = _cell_str(row[stem_col]) if stem_col < len(row) else ""
        options: list[SegmentedOption] = []
        seen_texts: set[str] = set()
        duplicate_text = False

        for lbl in ("A", "B", "C", "D", "E"):
            col_i = opt_cols.get(lbl)
            if col_i is None or col_i >= len(row):
                continue
            opt_text = _cell_str(row[col_i])
            if not opt_text:
                continue
            norm_opt = opt_text.lower()
            if norm_opt in seen_texts:
                duplicate_text = True
            seen_texts.add(norm_opt)
            options.append(
                SegmentedOption(
                    option_id=str(uuid.uuid4()),
                    label=lbl,
                    blocks=[{"type": "text", "text": opt_text}],
                    styled_clue=False,
                )
            )

        warnings: list[str] = []
        if not stem:
            warnings.append("EMPTY_QUESTION_BODY")
        if len(options) < 2:
            warnings.append("INSUFFICIENT_OPTIONS")
        if duplicate_text:
            warnings.append("DUPLICATE_OPTION_TEXT")

        raw_key = _cell_str(row[key_col]) if (key_col is not None and key_col < len(row)) else ""
        clean_key = raw_key.upper().rstrip(".) ")

        correct_ids: list[str] = []
        answer_status = "unknown"
        answer_provenance: str | None = None

        if len(clean_key) == 1 and clean_key in {"A", "B", "C", "D", "E"}:
            matched = [opt.option_id for opt in options if opt.label == clean_key]
            if matched:
                correct_ids = [matched[0]]
                answer_status = "confirmed"
                answer_provenance = f"xlsx_column:{profile}"
        elif raw_key:
            # Handle numeric 1..4 answer convention safely only if unambiguous digit in range
            if raw_key in {"1", "2", "3", "4"}:
                idx_lbl = "ABCD"[int(raw_key) - 1]
                matched = [opt.option_id for opt in options if opt.label == idx_lbl]
                if matched:
                    correct_ids = [matched[0]]
                    answer_status = "confirmed"
                    answer_provenance = f"xlsx_numeric_index:{profile}"
            else:
                warnings.append("ANSWER_NOT_FOUND")
        else:
            warnings.append("ANSWER_NOT_FOUND")

        if not correct_ids and "ANSWER_NOT_FOUND" not in warnings:
            warnings.append("ANSWER_NOT_FOUND")

        blocks = [{"type": "text", "text": stem}] if stem else []
        seg_conf = 0.95 if (stem and len(options) >= 4) else 0.5
        ans_conf = 0.95 if answer_status == "confirmed" else 0.0
        raw_preview = f"Dòng {row_offset}: {stem}\n" + " | ".join(
            f"{o.label}. {o.blocks[0]['text']}" for o in options
        )

        drafts.append(
            SegmentedQuestionDraft(
                position=len(drafts) + 1,
                source_number=row_offset,
                blocks=blocks,
                options=options,
                correct_option_ids=correct_ids,
                answer_status=answer_status,
                answer_provenance=answer_provenance,
                source_anchors=[f"xlsx:row={row_offset}"],
                raw_preview=raw_preview,
                warnings=list(dict.fromkeys(warnings)),
                confidence={"segmentation": seg_conf, "answer_detection": ans_conf},
            )
        )

    return drafts, {
        "profile_requested": profile,
        "has_header": bool(mapping["has_header"]),
        "detected_columns": {"stem": stem_col, "options": opt_cols, "key": key_col},
    }
