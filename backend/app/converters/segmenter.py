"""Question/option segmentation rule engine with provenance and non-guessing key policy."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.converters.docx_adapter import ContentBlock, ExtractedElement, ExtractedParagraph

QUESTION_START_RE = re.compile(
    r"^\s*(?:Câu|Question|Bài)\s*(\d+)\s*[:.)\-]?\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
OPTION_LINE_RE = re.compile(r"^\s*(?:\(?([A-E])\)?[\.\)])\s*(.*)$", re.DOTALL)
INLINE_OPTION_SPLIT_RE = re.compile(r"(?:(?<=^)|(?<=\s))\(?([A-E])\)?[\.\)]\s+")
ANSWER_KEY_HEADER_RE = re.compile(r"^\s*(?:ĐÁP\s*ÁN|BANG\s*DAP\s*AN|KEY)\b", re.IGNORECASE)
ANSWER_PAIR_RE = re.compile(r"(\d+)\s*[:.\-]?\s*([A-E])\b", re.IGNORECASE)
INLINE_CORRECT_RE = re.compile(
    r"^\s*(?:Đáp\s*án(?:\s*đúng)?|Key)\s*[:\-]\s*([A-E])\.?\s*$",
    re.IGNORECASE,
)


@dataclass
class SegmentedOption:
    option_id: str
    label: str  # "A", "B", "C", "D"
    blocks: list[dict[str, Any]]
    styled_clue: bool = False


@dataclass
class SegmentedQuestionDraft:
    position: int
    source_number: int | None
    blocks: list[dict[str, Any]]
    options: list[SegmentedOption]
    correct_option_ids: list[str]
    answer_status: str  # "confirmed" | "unknown" | "ambiguous"
    answer_provenance: str | None
    source_anchors: list[str]
    raw_preview: str
    warnings: list[str] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)


def _blocks_to_dicts(blocks: list[ContentBlock]) -> list[dict[str, Any]]:
    return [{"type": b.type, **b.data} for b in blocks]


def _has_answer_style_clue(para: ExtractedParagraph) -> bool:
    for text, clue in para.style_clues:
        if text.strip() and (clue.underline or clue.highlight or clue.colored):
            return True
    return False


def _strip_prefix_from_blocks(blocks: list[ContentBlock], prefix_len: int) -> list[ContentBlock]:
    remaining = prefix_len
    new_blocks: list[ContentBlock] = []
    for b in blocks:
        if b.type == "text" and remaining > 0:
            txt = str(b.data.get("text", ""))
            if len(txt) <= remaining:
                remaining -= len(txt)
                continue
            trimmed = txt[remaining:].lstrip()
            remaining = 0
            if trimmed:
                new_blocks.append(ContentBlock(type="text", data={"text": trimmed}))
        else:
            remaining = 0
            new_blocks.append(b)
    return new_blocks


def _split_inline_options(para: ExtractedParagraph) -> list[tuple[str, list[ContentBlock], bool]]:
    """Handle single-line multi-option paragraphs like 'A. 2   B. 4   C. 6   D. 8'."""
    text = para.plain_text
    matches = list(INLINE_OPTION_SPLIT_RE.finditer(text))
    if len(matches) < 2:
        m = OPTION_LINE_RE.match(text)
        if m:
            label = m.group(1).upper()
            prefix_len = len(text) - len(m.group(2))
            stripped = _strip_prefix_from_blocks(para.blocks, prefix_len)
            return [(label, stripped, _has_answer_style_clue(para))]
        return []

    # Check if paragraph has math/image blocks interleaved; if pure text, slice accurately
    has_non_text = any(b.type != "text" for b in para.blocks)
    if not has_non_text:
        results: list[tuple[str, list[ContentBlock], bool]] = []
        for idx, m in enumerate(matches):
            label = m.group(1).upper()
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            opt_text = text[start:end].strip()
            # Check if this option label/text carries underline/highlight/color clue
            clue_hit = False
            for clue_txt, clue in para.style_clues:
                if (clue.underline or clue.highlight or clue.colored) and (
                    f"{label}." in clue_txt or f"{label})" in clue_txt or (opt_text and opt_text in clue_txt)
                ):
                    clue_hit = True
                    break
            results.append((label, [ContentBlock(type="text", data={"text": opt_text})], clue_hit))
        return results

    # Mixed text + math/images in a single paragraph: split blocks around option markers
    # Fallback cleanly by splitting text blocks at option marker positions
    results_mixed: list[tuple[str, list[ContentBlock], bool]] = []
    current_label: str | None = None
    current_blocks: list[ContentBlock] = []
    for b in para.blocks:
        if b.type != "text":
            if current_label is not None:
                current_blocks.append(b)
            continue
        txt = str(b.data.get("text", ""))
        pos = 0
        for m in INLINE_OPTION_SPLIT_RE.finditer(txt):
            before = txt[pos : m.start()].strip()
            if before and current_label is not None:
                current_blocks.append(ContentBlock(type="text", data={"text": before}))
            if current_label is not None:
                results_mixed.append((current_label, current_blocks, False))
            current_label = m.group(1).upper()
            current_blocks = []
            pos = m.end()
        tail = txt[pos:].strip()
        if tail and current_label is not None:
            current_blocks.append(ContentBlock(type="text", data={"text": tail}))
    if current_label is not None:
        results_mixed.append((current_label, current_blocks, False))
    return results_mixed


def segment_elements(elements: list[ExtractedElement]) -> list[SegmentedQuestionDraft]:
    """Segment extracted paragraphs and tables into validated QuestionDraft candidates."""
    drafts: list[SegmentedQuestionDraft] = []
    end_key_map: dict[int, str] = {}
    in_end_key_block = False

    current_num: int | None = None
    current_blocks: list[ContentBlock] = []
    current_options: list[SegmentedOption] = []
    current_anchors: list[str] = []
    current_raw: list[str] = []
    current_warnings: list[str] = []
    inline_key_label: str | None = None

    def _flush_current() -> None:
        nonlocal current_num, current_blocks, current_options, current_anchors
        nonlocal current_raw, current_warnings, inline_key_label
        if not current_blocks and not current_options:
            return

        warnings = list(dict.fromkeys(current_warnings))
        if len(current_options) < 2:
            warnings.append("INSUFFICIENT_OPTIONS")
        if not current_blocks:
            warnings.append("EMPTY_QUESTION_BODY")

        # Determine answer key strictly without guessing
        correct_ids: list[str] = []
        answer_status = "unknown"
        provenance: str | None = None

        styled_options = [opt for opt in current_options if opt.styled_clue]
        if inline_key_label:
            matched = [opt.option_id for opt in current_options if opt.label == inline_key_label]
            if matched:
                correct_ids = [matched[0]]
                answer_status = "confirmed"
                provenance = "inline_key_marker"
        elif current_num is not None and current_num in end_key_map:
            target_lbl = end_key_map[current_num]
            matched = [opt.option_id for opt in current_options if opt.label == target_lbl]
            if matched:
                correct_ids = [matched[0]]
                answer_status = "confirmed"
                provenance = "end_answer_table"
        elif len(styled_options) == 1:
            correct_ids = [styled_options[0].option_id]
            answer_status = "confirmed"
            provenance = "run_style_clue"
        elif len(styled_options) > 1:
            answer_status = "ambiguous"
            provenance = "multiple_styled_options"
            warnings.append("MULTIPLE_KEYS_DETECTED")

        if not correct_ids and "MULTIPLE_KEYS_DETECTED" not in warnings:
            warnings.append("ANSWER_NOT_FOUND")

        seg_conf = 0.9 if (current_blocks and len(current_options) >= 4) else 0.55
        ans_conf = 0.85 if answer_status == "confirmed" else 0.0

        drafts.append(
            SegmentedQuestionDraft(
                position=len(drafts) + 1,
                source_number=current_num,
                blocks=_blocks_to_dicts(current_blocks),
                options=current_options,
                correct_option_ids=correct_ids,
                answer_status=answer_status,
                answer_provenance=provenance,
                source_anchors=current_anchors,
                raw_preview="\n".join(current_raw),
                warnings=list(dict.fromkeys(warnings)),
                confidence={
                    "segmentation": seg_conf,
                    "answer_detection": ans_conf,
                },
            )
        )
        current_num = None
        current_blocks = []
        current_options = []
        current_anchors = []
        current_raw = []
        current_warnings = []
        inline_key_label = None

    def _process_paragraph(para: ExtractedParagraph) -> None:
        nonlocal current_num, in_end_key_block, inline_key_label
        text = para.plain_text
        if not text and not para.blocks:
            return

        inline_key_match = INLINE_CORRECT_RE.match(text)
        if inline_key_match and (current_blocks or current_options):
            inline_key_label = inline_key_match.group(1).upper()
            current_raw.append(text)
            current_anchors.append(para.source_anchor)
            return

        if ANSWER_KEY_HEADER_RE.match(text):
            _flush_current()
            in_end_key_block = True
            for num_str, lbl in ANSWER_PAIR_RE.findall(text):
                end_key_map[int(num_str)] = lbl.upper()
            return

        if in_end_key_block:
            for num_str, lbl in ANSWER_PAIR_RE.findall(text):
                end_key_map[int(num_str)] = lbl.upper()
            return

        q_match = QUESTION_START_RE.match(text)
        if q_match:
            _flush_current()
            current_num = int(q_match.group(1))
            prefix_len = len(text) - len(q_match.group(2))
            stem_blocks = _strip_prefix_from_blocks(para.blocks, prefix_len)
            current_blocks.extend(stem_blocks)
            current_anchors.append(para.source_anchor)
            current_raw.append(text)
            current_warnings.extend(para.warnings)
            return

        opts = _split_inline_options(para)
        if opts:
            current_anchors.append(para.source_anchor)
            current_raw.append(text)
            current_warnings.extend(para.warnings)
            for lbl, opt_blocks, clue_hit in opts:
                current_options.append(
                    SegmentedOption(
                        option_id=str(uuid.uuid4()),
                        label=lbl,
                        blocks=_blocks_to_dicts(opt_blocks),
                        styled_clue=clue_hit,
                    )
                )
            return

        if current_num is not None or current_blocks:
            current_blocks.extend(para.blocks)
            current_anchors.append(para.source_anchor)
            current_raw.append(text)
            current_warnings.extend(para.warnings)

    for elem in elements:
        if elem.kind == "paragraph" and elem.paragraph is not None:
            _process_paragraph(elem.paragraph)
        elif elem.kind == "table" and elem.table is not None:
            # Check if table is an answer-key grid
            flat_cells = [c.plain_text for row in elem.table.rows for c in row if c.plain_text]
            joined = " ".join(flat_cells)
            has_key_header = ANSWER_KEY_HEADER_RE.search(joined)
            if in_end_key_block or (has_key_header and len(ANSWER_PAIR_RE.findall(joined)) >= 1):
                _flush_current()
                in_end_key_block = True
                for num_str, lbl in ANSWER_PAIR_RE.findall(joined):
                    end_key_map[int(num_str)] = lbl.upper()
                continue

            # Otherwise process cells in reading order (supports 2-column A/B/C/D option tables!)
            for row in elem.table.rows:
                for cell in row:
                    _process_paragraph(cell)

    _flush_current()

    # Apply end_key_map retrospectively if end key block appeared after questions
    if end_key_map:
        for d in drafts:
            if d.source_number is not None and d.source_number in end_key_map and not d.correct_option_ids:
                target_lbl = end_key_map[d.source_number]
                matched = [opt.option_id for opt in d.options if opt.label == target_lbl]
                if matched:
                    d.correct_option_ids = [matched[0]]
                    d.answer_status = "confirmed"
                    d.answer_provenance = "end_answer_table"
                    d.confidence["answer_detection"] = 0.9
                    if "ANSWER_NOT_FOUND" in d.warnings:
                        d.warnings.remove("ANSWER_NOT_FOUND")
    return drafts
