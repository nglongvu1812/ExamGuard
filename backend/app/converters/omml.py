"""OOXML OMML (<m:oMath> / <m:oMathPara>) converter to LaTeX with safe fallback tracking."""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

NARY_SYMBOLS: dict[str, str] = {
    "∑": r"\sum",
    "∏": r"\prod",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "⋃": r"\bigcup",
    "⋂": r"\bigcap",
}

UNICODE_TO_LATEX: dict[str, str] = {
    "≤": r"\le ",
    "≥": r"\ge ",
    "≠": r"\ne ",
    "≈": r"\approx ",
    "±": r"\pm ",
    "∓": r"\mp ",
    "×": r"\times ",
    "÷": r"\div ",
    "⋅": r"\cdot ",
    "∞": r"\infty ",
    "→": r"\to ",
    "⇒": r"\Rightarrow ",
    "⇔": r"\Leftrightarrow ",
    "∈": r"\in ",
    "∉": r"\notin ",
    "⊂": r"\subset ",
    "⊆": r"\subseteq ",
    "∪": r"\cup ",
    "∩": r"\cap ",
    "∀": r"\forall ",
    "∃": r"\exists ",
    "π": r"\pi ",
    "α": r"\alpha ",
    "β": r"\beta ",
    "γ": r"\gamma ",
    "δ": r"\delta ",
    "Δ": r"\Delta ",
    "θ": r"\theta ",
    "λ": r"\lambda ",
    "φ": r"\varphi ",
    "ω": r"\omega ",
    "Ω": r"\Omega ",
    "°": r"^\circ ",
}

ACCENT_MAP: dict[str, str] = {
    "\u20d7": r"\vec",
    "→": r"\vec",
    "\u0304": r"\bar",
    "¯": r"\bar",
    "\u0302": r"\hat",
    "^": r"\hat",
    "\u0303": r"\tilde",
}


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _get_val(node: etree._Element | None, default: str = "") -> str:
    if node is None:
        return default
    for attr_name in (f"{{{OMML_NS}}}val", "val"):
        val = node.get(attr_name)
        if val is not None:
            return str(val)
    return default


def _translate_text(text: str) -> str:
    out: list[str] = []
    for ch in text:
        out.append(UNICODE_TO_LATEX.get(ch, ch))
    return "".join(out)


def _omml_children_to_latex(element: etree._Element) -> tuple[str, bool]:
    parts: list[str] = []
    had_warning = False
    for child in element:
        latex, warn = _node_to_latex(child)
        parts.append(latex)
        had_warning = had_warning or warn
    return "".join(parts), had_warning


def _child_by_local(element: etree._Element, name: str) -> etree._Element | None:
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _node_to_latex(node: etree._Element) -> tuple[str, bool]:
    tag = _local(node.tag)

    if tag in {"oMathPara", "oMath", "e", "num", "den", "sub", "sup", "deg", "fName"}:
        return _omml_children_to_latex(node)

    if tag == "r":
        texts = [el.text or "" for el in node.iter() if _local(el.tag) == "t"]
        return _translate_text("".join(texts)), False

    if tag == "f":
        num_el = _child_by_local(node, "num")
        den_el = _child_by_local(node, "den")
        num_tex, w1 = _omml_children_to_latex(num_el) if num_el is not None else ("", True)
        den_tex, w2 = _omml_children_to_latex(den_el) if den_el is not None else ("", True)
        return rf"\frac{{{num_tex}}}{{{den_tex}}}", (w1 or w2)

    if tag == "rad":
        deg_el = _child_by_local(node, "deg")
        e_el = _child_by_local(node, "e")
        body_tex, w1 = _omml_children_to_latex(e_el) if e_el is not None else ("", True)
        deg_tex, w2 = _omml_children_to_latex(deg_el) if deg_el is not None else ("", False)
        if deg_tex.strip():
            return rf"\sqrt[{deg_tex.strip()}]{{{body_tex}}}", (w1 or w2)
        return rf"\sqrt{{{body_tex}}}", (w1 or w2)

    if tag == "sSup":
        e_el = _child_by_local(node, "e")
        sup_el = _child_by_local(node, "sup")
        base, w1 = _omml_children_to_latex(e_el) if e_el is not None else ("", True)
        sup, w2 = _omml_children_to_latex(sup_el) if sup_el is not None else ("", True)
        return f"{{{base}}}^{{{sup}}}", (w1 or w2)

    if tag == "sSub":
        e_el = _child_by_local(node, "e")
        sub_el = _child_by_local(node, "sub")
        base, w1 = _omml_children_to_latex(e_el) if e_el is not None else ("", True)
        sub, w2 = _omml_children_to_latex(sub_el) if sub_el is not None else ("", True)
        return f"{{{base}}}_{{{sub}}}", (w1 or w2)

    if tag == "sSubSup":
        e_el = _child_by_local(node, "e")
        sub_el = _child_by_local(node, "sub")
        sup_el = _child_by_local(node, "sup")
        base, w1 = _omml_children_to_latex(e_el) if e_el is not None else ("", True)
        sub, w2 = _omml_children_to_latex(sub_el) if sub_el is not None else ("", True)
        sup, w3 = _omml_children_to_latex(sup_el) if sup_el is not None else ("", True)
        return f"{{{base}}}_{{{sub}}}^{{{sup}}}", (w1 or w2 or w3)

    if tag == "d":
        pr = _child_by_local(node, "dPr")
        beg = _get_val(_child_by_local(pr, "begChr") if pr is not None else None, "(") or "("
        end = _get_val(_child_by_local(pr, "endChr") if pr is not None else None, ")") or ")"
        beg_tex = r"\{" if beg == "{" else beg
        end_tex = r"\}" if end == "}" else end
        elems = [_omml_children_to_latex(ch) for ch in node if _local(ch.tag) == "e"]
        joined = ", ".join(tex for tex, _ in elems)
        warn = any(w for _, w in elems)
        return rf"\left{beg_tex}{joined}\right{end_tex}", warn

    if tag == "nary":
        pr = _child_by_local(node, "naryPr")
        chr_val = _get_val(_child_by_local(pr, "chr") if pr is not None else None, "∑")
        op = NARY_SYMBOLS.get(chr_val, r"\sum")
        sub_el = _child_by_local(node, "sub")
        sup_el = _child_by_local(node, "sup")
        e_el = _child_by_local(node, "e")
        sub_tex, w1 = _omml_children_to_latex(sub_el) if sub_el is not None else ("", False)
        sup_tex, w2 = _omml_children_to_latex(sup_el) if sup_el is not None else ("", False)
        body_tex, w3 = _omml_children_to_latex(e_el) if e_el is not None else ("", True)
        limits = ""
        if sub_tex.strip():
            limits += f"_{{{sub_tex.strip()}}}"
        if sup_tex.strip():
            limits += f"^{{{sup_tex.strip()}}}"
        return f"{op}{limits} {body_tex}", (w1 or w2 or w3)

    if tag == "func":
        fname_el = _child_by_local(node, "fName")
        e_el = _child_by_local(node, "e")
        fn_tex, w1 = _omml_children_to_latex(fname_el) if fname_el is not None else ("", False)
        body_tex, w2 = _omml_children_to_latex(e_el) if e_el is not None else ("", False)
        fn_clean = fn_tex.strip()
        if fn_clean in {"lim", "sin", "cos", "tan", "cot", "log", "ln", "exp"}:
            return rf"\{fn_clean} {body_tex}", (w1 or w2)
        return f"{fn_clean} {body_tex}", (w1 or w2)

    if tag == "limLow":
        e_el = _child_by_local(node, "e")
        lim_el = _child_by_local(node, "lim")
        base, w1 = _omml_children_to_latex(e_el) if e_el is not None else ("", False)
        lim_tex, w2 = _omml_children_to_latex(lim_el) if lim_el is not None else ("", False)
        base_clean = base.strip()
        if base_clean == "lim":
            base_clean = r"\lim"
        return f"{base_clean}_{{{lim_tex.strip()}}}", (w1 or w2)

    if tag == "acc":
        pr = _child_by_local(node, "accPr")
        chr_val = _get_val(_child_by_local(pr, "chr") if pr is not None else None, "\u0302")
        cmd = ACCENT_MAP.get(chr_val, r"\hat")
        e_el = _child_by_local(node, "e")
        body_tex, w = _omml_children_to_latex(e_el) if e_el is not None else ("", True)
        return rf"{cmd}{{{body_tex}}}", w

    if tag == "m":
        rows_tex: list[str] = []
        warn = False
        for mr in node:
            if _local(mr.tag) == "mr":
                cells: list[str] = []
                for cell in mr:
                    if _local(cell.tag) == "e":
                        ctex, cw = _omml_children_to_latex(cell)
                        cells.append(ctex.strip())
                        warn = warn or cw
                rows_tex.append(" & ".join(cells))
        body = r" \\ ".join(rows_tex)
        return rf"\begin{{pmatrix}}{body}\end{{pmatrix}}", warn

    if tag in {"ctrlPr", "rPr", "fPr", "radPr", "dPr", "naryPr", "accPr", "mPr"}:
        return "", False

    # Fallback: traverse unknown OMML wrappers cleanly and flag warning
    tex, child_warn = _omml_children_to_latex(node)
    return tex, True if not tex else child_warn


@dataclass(frozen=True)
class OmmlConvertResult:
    latex: str
    omml_xml: str
    parse_warning: bool


def convert_omml_to_latex(omml_element: etree._Element) -> OmmlConvertResult:
    """Convert an OMML element to LaTeX while preserving raw XML provenance."""
    raw_xml = etree.tostring(omml_element, encoding="unicode")
    try:
        latex, warn = _node_to_latex(omml_element)
        clean = latex.strip()
        if not clean:
            return OmmlConvertResult(latex="", omml_xml=raw_xml, parse_warning=True)
        return OmmlConvertResult(latex=clean, omml_xml=raw_xml, parse_warning=warn)
    except Exception:
        return OmmlConvertResult(latex="", omml_xml=raw_xml, parse_warning=True)
