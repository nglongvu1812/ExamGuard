"""DOCX OOXML adapter extracting ordered ContentNodes (text, math, images, tables, formatting clues)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.converters.ingest import store_media_asset
from app.converters.omml import convert_omml_to_latex
from lxml import etree
from sqlalchemy.orm import Session

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V_NS = "urn:schemas-microsoft-com:vml"

SAFE_XML_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    load_dtd=False,
)


@dataclass
class RunStyleClue:
    bold: bool = False
    underline: bool = False
    highlight: bool = False
    colored: bool = False


@dataclass
class ContentBlock:
    type: str  # "text" | "math" | "image" | "table"
    data: dict[str, Any]


@dataclass
class ExtractedParagraph:
    index: int
    source_anchor: str
    blocks: list[ContentBlock] = field(default_factory=list)
    plain_text: str = ""
    style_clues: list[tuple[str, RunStyleClue]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractedTable:
    index: int
    source_anchor: str
    rows: list[list[ExtractedParagraph]]


@dataclass
class ExtractedElement:
    kind: str  # "paragraph" | "table"
    paragraph: ExtractedParagraph | None = None
    table: ExtractedTable | None = None


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _read_relationships(zf: zipfile.ZipFile) -> dict[str, tuple[str, str]]:
    rels: dict[str, tuple[str, str]] = {}
    if "word/_rels/document.xml.rels" not in zf.namelist():
        return rels
    xml_bytes = zf.read("word/_rels/document.xml.rels")
    root = etree.fromstring(xml_bytes, parser=SAFE_XML_PARSER)
    for rel in root:
        rid = rel.get("Id")
        target = rel.get("Target")
        mode = rel.get("TargetMode") or "Internal"
        if rid and target:
            rels[rid] = (target, mode)
    return rels


def _extract_run_style(r_el: etree._Element) -> RunStyleClue:
    rpr = r_el.find(f"{{{W_NS}}}rPr")
    if rpr is None:
        return RunStyleClue()

    def _is_on(tag_name: str) -> bool:
        el = rpr.find(f"{{{W_NS}}}{tag_name}")
        if el is None:
            return False
        val = el.get(f"{{{W_NS}}}val")
        return val not in {"0", "false", "none"}

    bold = _is_on("b")
    underline = _is_on("u")
    highlight = _is_on("highlight")
    color_el = rpr.find(f"{{{W_NS}}}color")
    colored = False
    if color_el is not None:
        cval = (color_el.get(f"{{{W_NS}}}val") or "").lower()
        if cval and cval not in {"auto", "000000", "000"}:
            colored = True
    return RunStyleClue(bold=bold, underline=underline, highlight=highlight, colored=colored)


def _extract_image_from_rid(
    zf: zipfile.ZipFile,
    rels: dict[str, tuple[str, str]],
    rid: str,
    db: Session,
    assets_dir: Path,
) -> tuple[ContentBlock | None, str | None]:
    rel = rels.get(rid)
    if not rel:
        return None, "MISSING_IMAGE_RELATION"
    target, mode = rel
    if mode.lower() == "external" or target.lower().startswith(("http://", "https://")):
        return None, "EXTERNAL_IMAGE_BLOCKED"
    zip_member = target.lstrip("/")
    if not zip_member.startswith("word/"):
        zip_member = f"word/{zip_member}"
    zip_member = zip_member.replace("word/../", "")
    if zip_member not in zf.namelist():
        return None, "MISSING_IMAGE_BINARY"

    img_bytes = zf.read(zip_member)
    asset = store_media_asset(db, assets_dir=assets_dir, filename=zip_member, content=img_bytes)
    warn = "LEGACY_VECTOR_IMAGE" if asset.mime_type in {"image/x-wmf", "image/x-emf"} else None
    return ContentBlock(
        type="image",
        data={
            "asset_id": asset.id,
            "mime_type": asset.mime_type,
            "alt": Path(zip_member).name,
        },
    ), warn


def _extract_paragraph(
    p_el: etree._Element,
    *,
    anchor: str,
    index: int,
    zf: zipfile.ZipFile,
    rels: dict[str, tuple[str, str]],
    db: Session,
    assets_dir: Path,
) -> ExtractedParagraph:
    blocks: list[ContentBlock] = []
    style_clues: list[tuple[str, RunStyleClue]] = []
    warnings: list[str] = []
    text_fragments: list[str] = []

    def _append_text(txt: str, clue: RunStyleClue) -> None:
        if not txt:
            return
        text_fragments.append(txt)
        style_clues.append((txt, clue))
        if blocks and blocks[-1].type == "text":
            blocks[-1].data["text"] += txt
        else:
            blocks.append(ContentBlock(type="text", data={"text": txt}))

    for child in p_el:
        tag = _local(child.tag)
        if tag == "r":
            clue = _extract_run_style(child)
            for sub in child:
                sub_tag = _local(sub.tag)
                if sub_tag == "t":
                    _append_text(sub.text or "", clue)
                elif sub_tag == "tab":
                    _append_text(" ", clue)
                elif sub_tag == "br":
                    _append_text("\n", clue)
                elif sub_tag in {"drawing", "pict"}:
                    # Handle both inline & anchored drawing blips + VML imagedata
                    blips = list(sub.iter(f"{{{A_NS}}}blip"))
                    vml_imgs = list(sub.iter(f"{{{V_NS}}}imagedata"))
                    for blip in blips:
                        rid = blip.get(f"{{{R_NS}}}embed") or blip.get(f"{{{R_NS}}}link")
                        if rid:
                            img_block, warn = _extract_image_from_rid(zf, rels, rid, db, assets_dir)
                            if img_block:
                                blocks.append(img_block)
                            if warn:
                                warnings.append(warn)
                    for vimg in vml_imgs:
                        rid = vimg.get(f"{{{R_NS}}}id")
                        if rid:
                            img_block, warn = _extract_image_from_rid(zf, rels, rid, db, assets_dir)
                            if img_block:
                                blocks.append(img_block)
                            if warn:
                                warnings.append(warn)
                elif sub_tag == "object":
                    # Legacy MathType / OLE object: try preserving fallback VML image
                    vml_imgs = list(sub.iter(f"{{{V_NS}}}imagedata"))
                    for vimg in vml_imgs:
                        rid = vimg.get(f"{{{R_NS}}}id")
                        if rid:
                            img_block, _warn = _extract_image_from_rid(zf, rels, rid, db, assets_dir)
                            if img_block:
                                blocks.append(img_block)
                    warnings.append("MATH_FALLBACK_IMAGE")
        elif tag in {"oMath", "oMathPara"}:
            res = convert_omml_to_latex(child)
            if res.parse_warning:
                warnings.append("MATH_PARSE_WARNING")
            blocks.append(
                ContentBlock(
                    type="math",
                    data={
                        "latex": res.latex,
                        "omml_xml": res.omml_xml,
                        "parse_warning": res.parse_warning,
                    },
                )
            )
            if res.latex:
                text_fragments.append(f" {res.latex} ")
        elif tag == "hyperlink":
            for r_sub in child.findall(f"{{{W_NS}}}r"):
                clue = _extract_run_style(r_sub)
                for t_sub in r_sub.findall(f"{{{W_NS}}}t"):
                    _append_text(t_sub.text or "", clue)

    return ExtractedParagraph(
        index=index,
        source_anchor=anchor,
        blocks=blocks,
        plain_text="".join(text_fragments).strip(),
        style_clues=style_clues,
        warnings=list(dict.fromkeys(warnings)),
    )


def extract_docx_elements(
    content: bytes,
    *,
    db: Session,
    assets_dir: Path,
) -> list[ExtractedElement]:
    """Parse word/document.xml preserving exact paragraph and table order."""
    elements: list[ExtractedElement] = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        rels = _read_relationships(zf)
        doc_xml = zf.read("word/document.xml")
        root = etree.fromstring(doc_xml, parser=SAFE_XML_PARSER)
        body = root.find(f"{{{W_NS}}}body")
        if body is None:
            return elements

        p_counter = 0
        t_counter = 0
        for child in body:
            tag = _local(child.tag)
            if tag == "p":
                para = _extract_paragraph(
                    child,
                    anchor=f"p:{p_counter}",
                    index=p_counter,
                    zf=zf,
                    rels=rels,
                    db=db,
                    assets_dir=assets_dir,
                )
                elements.append(ExtractedElement(kind="paragraph", paragraph=para))
                p_counter += 1
            elif tag == "tbl":
                rows: list[list[ExtractedParagraph]] = []
                for r_idx, tr in enumerate(child.findall(f"{{{W_NS}}}tr")):
                    row_cells: list[ExtractedParagraph] = []
                    for c_idx, tc in enumerate(tr.findall(f"{{{W_NS}}}tc")):
                        cell_paras = [
                            _extract_paragraph(
                                p_el,
                                anchor=f"tbl:{t_counter}:r{r_idx}:c{c_idx}",
                                index=p_counter,
                                zf=zf,
                                rels=rels,
                                db=db,
                                assets_dir=assets_dir,
                            )
                            for p_el in tc.findall(f"{{{W_NS}}}p")
                        ]
                        # Merge paragraphs in same cell cleanly preserving order
                        merged_blocks: list[ContentBlock] = []
                        merged_clues: list[tuple[str, RunStyleClue]] = []
                        merged_warnings: list[str] = []
                        merged_text: list[str] = []
                        for cp in cell_paras:
                            if merged_blocks and cp.blocks:
                                merged_blocks.append(ContentBlock(type="text", data={"text": "\n"}))
                            merged_blocks.extend(cp.blocks)
                            merged_clues.extend(cp.style_clues)
                            merged_warnings.extend(cp.warnings)
                            if cp.plain_text:
                                merged_text.append(cp.plain_text)
                        row_cells.append(
                            ExtractedParagraph(
                                index=p_counter,
                                source_anchor=f"tbl:{t_counter}:r{r_idx}:c{c_idx}",
                                blocks=merged_blocks,
                                plain_text="\n".join(merged_text).strip(),
                                style_clues=merged_clues,
                                warnings=list(dict.fromkeys(merged_warnings)),
                            )
                        )
                    rows.append(row_cells)
                elements.append(
                    ExtractedElement(
                        kind="table",
                        table=ExtractedTable(index=t_counter, source_anchor=f"tbl:{t_counter}", rows=rows),
                    )
                )
                t_counter += 1
    return elements
