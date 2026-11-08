"""P2 Converter tests: DOCX text/table/image/OMML, non-guessing keys, approval, and security."""

from __future__ import annotations

import io
import struct
import zipfile
import zlib
from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from docx import Document
from docx.oxml import parse_xml
from fastapi.testclient import TestClient


def _make_minimal_png() -> bytes:
    """Create a valid 1x1 PNG image in memory (no external asset needed)."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xFF\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _teacher_headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/v1/auth/teacher/local-session").json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_docx_text_inline_options_omml_and_image_pipeline(tmp_path: Path) -> None:
    doc = Document()

    # Question 1: OMML fraction + inline options + end answer table
    p1 = doc.add_paragraph("Câu 1: Tính giá trị biểu thức ")
    omml_frac = parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<m:f><m:num><m:r><m:t>1</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f>"
        "</m:oMath>"
    )
    p1._p.append(omml_frac)
    doc.add_paragraph("A. 0.5   B. 1.5   C. 2.5   D. 3.5")

    # Question 2: Table-based 2x2 options + embedded PNG image in stem
    doc.add_paragraph("Câu 2: Quan sát hình sau:")
    img_path = tmp_path / "sample.png"
    img_path.write_bytes(_make_minimal_png())
    doc.add_picture(str(img_path))
    tbl = doc.add_table(rows=2, cols=2)
    tbl.cell(0, 0).text = "A. Hình vuông"
    tbl.cell(0, 1).text = "B. Hình tròn"
    tbl.cell(1, 0).text = "C. Tam giác"
    tbl.cell(1, 1).text = "D. Hình thang"

    # Question 3: No answer key provided -> must stay unknown, never guessed!
    doc.add_paragraph("Câu 3: Thủ đô của Việt Nam là thành phố nào?")
    doc.add_paragraph("A. Hà Nội")
    doc.add_paragraph("B. Đà Nẵng")
    doc.add_paragraph("C. Huế")
    doc.add_paragraph("D. Cần Thơ")

    # End answer key block only for Q1 and Q2
    doc.add_paragraph("ĐÁP ÁN: 1A 2C")

    docx_buf = io.BytesIO()
    doc.save(docx_buf)

    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        res = client.post(
            "/api/v1/questions/import",
            files={
                "file": (
                    "de_toan_mau.docx",
                    docx_buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["summary"]["total_questions"] == 3
        drafts = data["drafts"]

        # Q1: OMML converted to \frac{1}{2}, 4 options parsed, key A confirmed
        q1 = drafts[0]
        math_blocks = [b for b in q1["blocks"] if b["type"] == "math"]
        assert len(math_blocks) == 1
        assert r"\frac{1}{2}" in math_blocks[0]["latex"]
        assert len(q1["options"]) == 4
        assert q1["answer"]["status"] == "confirmed"
        assert len(q1["answer"]["correct_option_ids"]) == 1

        # Q2: embedded image stored & servable via /api/v1/assets/{id}, 4 table options parsed, key C confirmed
        q2 = drafts[1]
        img_blocks = [b for b in q2["blocks"] if b["type"] == "image"]
        assert len(img_blocks) == 1
        asset_id = img_blocks[0]["asset_id"]
        asset_res = client.get(f"/api/v1/assets/{asset_id}")
        assert asset_res.status_code == 200
        assert asset_res.headers["x-content-type-options"] == "nosniff"
        assert len(q2["options"]) == 4
        assert q2["answer"]["status"] == "confirmed"

        # Q3: Missing answer key -> MUST be flagged unknown and CANNOT be auto-approved
        q3 = drafts[2]
        assert q3["answer"]["status"] == "unknown"
        assert "ANSWER_NOT_FOUND" in q3["warnings"]
        approve_fail = client.post(f"/api/v1/questions/drafts/{q3['id']}/approve", headers=headers)
        assert approve_fail.status_code == 400

        # Batch approve-ready approves Q1 and Q2 (2) and skips Q3 (1)
        batch = client.post(f"/api/v1/questions/import/{data['job_id']}/approve-ready", headers=headers)
        assert batch.status_code == 200
        assert batch.json() == {"approved_count": 2, "skipped_count": 1}

        # Teacher manually sets Q3 key -> approve succeeds -> bank now has 3 immutable questions
        opt_a_id = q3["options"][0]["option_id"]
        patch_q3 = client.patch(
            f"/api/v1/questions/drafts/{q3['id']}",
            json={"correct_option_ids": [opt_a_id]},
            headers=headers,
        )
        assert patch_q3.status_code == 200
        assert "ANSWER_NOT_FOUND" not in patch_q3.json()["warnings"]

        approve_q3 = client.post(f"/api/v1/questions/drafts/{q3['id']}/approve", headers=headers)
        assert approve_q3.status_code == 200
        assert approve_q3.json()["status"] == "APPROVED"

        bank = client.get("/api/v1/questions/bank", headers=headers).json()
        assert len(bank) == 3


def test_docx_ambiguous_multiple_styled_keys_flagged(tmp_path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Câu 1: Chọn phương án đúng:")
    p_a = doc.add_paragraph()
    r_a = p_a.add_run("A. Phương án một")
    r_a.underline = True
    p_b = doc.add_paragraph()
    r_b = p_b.add_run("B. Phương án hai")
    r_b.underline = True

    buf = io.BytesIO()
    doc.save(buf)

    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        res = client.post(
            "/api/v1/questions/import",
            files={"file": ("ambiguous.docx", buf.getvalue(), mime)},
            headers=headers,
        )
        assert res.status_code == 201
        q1 = res.json()["drafts"][0]
        assert q1["answer"]["status"] == "ambiguous"
        assert "MULTIPLE_KEYS_DETECTED" in q1["warnings"]
        assert q1["answer"]["correct_option_ids"] == []


def test_malformed_zip_bomb_and_path_traversal_security(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)

        # 1. Fake non-DOCX file
        r1 = client.post(
            "/api/v1/questions/import",
            files={"file": ("fake.docx", b"NOT_A_ZIP_HEADER", "application/octet-stream")},
            headers=headers,
        )
        assert r1.status_code == 400

        # 2. Path traversal entry inside ZIP
        traversal_buf = io.BytesIO()
        with zipfile.ZipFile(traversal_buf, "w") as zf:
            zf.writestr("../../evil.txt", "bad")
            zf.writestr("word/document.xml", "<w:document/>")
        r2 = client.post(
            "/api/v1/questions/import",
            files={"file": ("traversal.docx", traversal_buf.getvalue(), "application/zip")},
            headers=headers,
        )
        assert r2.status_code == 400
        assert "path traversal" in r2.json()["detail"].lower()

        # 3. Zip bomb (extreme compression ratio > 100x)
        bomb_buf = io.BytesIO()
        with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", "A" * 500_000)
        r3 = client.post(
            "/api/v1/questions/import",
            files={"file": ("bomb.docx", bomb_buf.getvalue(), "application/zip")},
            headers=headers,
        )
        assert r3.status_code == 400

        # 4. Asset path traversal blocked
        r4 = client.get("/api/v1/assets/..%2F..%2Fsecret")
        assert r4.status_code in {400, 404}


def test_omml_all_supported_constructs() -> None:
    from app.converters.omml import convert_omml_to_latex
    from lxml import etree as lxml_etree

    omml_ns = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
    samples = [
        (
            f"<m:oMath {omml_ns}><m:rad><m:deg><m:r><m:t>3</m:t></m:r></m:deg>"
            "<m:e><m:r><m:t>8</m:t></m:r></m:e></m:rad></m:oMath>",
            r"\sqrt[3]{8}",
        ),
        (
            f"<m:oMath {omml_ns}><m:sSubSup><m:e><m:r><m:t>x</m:t></m:r></m:e>"
            "<m:sub><m:r><m:t>i</m:t></m:r></m:sub><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSubSup></m:oMath>",
            "{x}_{i}^{2}",
        ),
        (
            f"<m:oMath {omml_ns}><m:limLow><m:e><m:r><m:t>lim</m:t></m:r></m:e>"
            "<m:lim><m:r><m:t>x→2</m:t></m:r></m:lim></m:limLow></m:oMath>",
            r"\lim_{x\to 2}",
        ),
        (
            f'<m:oMath {omml_ns}><m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr>'
            "<m:sub><m:r><m:t>k=1</m:t></m:r></m:sub><m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
            "<m:e><m:r><m:t>k</m:t></m:r></m:e></m:nary></m:oMath>",
            r"\sum_{k=1}^{n} k",
        ),
        (
            f"<m:oMath {omml_ns}><m:m><m:mr><m:e><m:r><m:t>1</m:t></m:r></m:e>"
            "<m:e><m:r><m:t>0</m:t></m:r></m:e></m:mr></m:m></m:oMath>",
            r"\begin{pmatrix}1 & 0\end{pmatrix}",
        ),
    ]
    for xml_str, expected_sub in samples:
        res = convert_omml_to_latex(lxml_etree.fromstring(xml_str))
        assert expected_sub in res.latex
        assert not res.parse_warning


def test_external_image_blocked_and_benchmark_categories(tmp_path: Path) -> None:
    # Build raw DOCX OOXML containing an External image link -> MUST block & flag offline
    ext_docx = io.BytesIO()
    with zipfile.ZipFile(ext_docx, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            "</Types>",
        )
        zf.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rExt1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="https://example.invalid/tracker.png" TargetMode="External"/>'
            "</Relationships>",
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<w:body>"
            "<w:p><w:r><w:t>Câu 1: Câu thiếu đáp án?</w:t></w:r>"
            "<w:r><w:drawing><a:blip r:link=\"rExt1\"/></w:drawing></w:r></w:p>"
            "<w:p><w:r><w:t>A. Đúng</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Câu 2: Câu đầy đủ?</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>A. Một   B. Hai   C. Ba   D. Bốn</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Đáp án: B</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )

    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        res = client.post(
            "/api/v1/questions/import",
            files={"file": ("bench.docx", ext_docx.getvalue(), mime)},
            headers=headers,
        )
        assert res.status_code == 201
        drafts = res.json()["drafts"]
        assert len(drafts) == 2
        # Q1 has external image blocked + <2 options + missing key -> flagged honestly
        assert "EXTERNAL_IMAGE_BLOCKED" in drafts[0]["warnings"]
        assert "INSUFFICIENT_OPTIONS" in drafts[0]["warnings"]
        assert "ANSWER_NOT_FOUND" in drafts[0]["warnings"]
        # Q2 has 4 options + inline key -> confirmed
        assert drafts[1]["answer"]["status"] == "confirmed"
        assert drafts[1]["warnings"] == []

        # Security: unauthenticated user cannot access teacher question bank or import
        unauth = client.get("/api/v1/questions/bank")
        assert unauth.status_code in {401, 403}
