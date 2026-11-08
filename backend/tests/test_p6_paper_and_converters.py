"""P6 tests: paper exam booklets, OMR rectification/scoring/review bridge, PDF & XLSX converters."""

from __future__ import annotations

import hashlib
import io
import json
import time
import uuid
from pathlib import Path
from typing import Any

import openpyxl
import pypdf
from app.core.config import Settings
from app.db.models import (
    AnswerKeyVersion,
    OmrScanSubmission,
    Question,
    QuestionVersion,
)
from app.main import create_app
from app.services.export_service import ensure_pdf_fonts
from app.services.paper_service import render_omr_template_png
from fastapi.testclient import TestClient
from PIL import Image, ImageEnhance
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas


def _teacher_headers(client: TestClient) -> dict[str, str]:
    res = client.post("/api/v1/auth/teacher/local-session")
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _seed_rich_questions(client: TestClient) -> list[dict[str, Any]]:
    app = client.app
    settings: Settings = app.state.settings  # type: ignore[attr-defined]
    session_factory = app.state.session_factory  # type: ignore[attr-defined]

    # Store a valid 16x16 local raster PNG asset into ExamGuardData/assets
    img_buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(30, 58, 95)).save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()
    sha = hashlib.sha256(img_bytes).hexdigest()
    asset_dir = settings.assets_dir / sha[:2]
    asset_dir.mkdir(parents=True, exist_ok=True)
    relpath = f"{sha[:2]}/{sha}.png"
    (settings.assets_dir / relpath).write_bytes(img_bytes)

    seeded: list[dict[str, Any]] = []
    with session_factory() as db:
        from app.db.models import Asset

        db.add(Asset(id=sha, mime_type="image/png", byte_size=len(img_bytes), relpath=relpath))
        db.flush()

        for idx in range(1, 5):
            qid = str(uuid.uuid4())
            qvid = str(uuid.uuid4())
            opt_ids = [str(uuid.uuid4()) for _ in range(4)]
            blocks: list[dict[str, Any]] = [{"type": "text", "text": f"Câu hỏi số {idx}: Tính giá trị"}]
            if idx == 1:
                blocks.append({"type": "math", "latex": r"\frac{1}{2} + \sqrt{4}"})
            if idx == 2:
                blocks.append({"type": "image", "asset_id": sha, "alt": "Hình minh họa"})

            q = Question(id=qid, bank_name="Toán P6", active_version_id=qvid)
            qv = QuestionVersion(
                id=qvid,
                question_id=qid,
                version_number=1,
                content_blocks_json=json.dumps(blocks, ensure_ascii=False),
                options_json=json.dumps(
                    [
                        {
                            "option_id": opt_ids[i],
                            "label": "ABCD"[i],
                            "blocks": [{"type": "text", "text": f"Phương án {'ABCD'[i]} câu {idx}"}],
                        }
                        for i in range(4)
                    ],
                    ensure_ascii=False,
                ),
                provenance_json="{}",
                approved_by=1,
            )
            kv = AnswerKeyVersion(
                id=str(uuid.uuid4()),
                question_version_id=qvid,
                version_number=1,
                correct_option_ids_json=json.dumps([opt_ids[0]]),
                reason="Đáp án gốc",
                approved_by=1,
            )
            db.add(q)
            db.flush()
            db.add(qv)
            db.flush()
            db.add(kv)
            db.flush()
            seeded.append({"qvid": qvid, "opt_a": opt_ids[0], "opt_ids": opt_ids})
        db.commit()
    return seeded


def _setup_two_student_class_and_exam(
    client: TestClient, hdrs: dict[str, str], qvids: list[str]
) -> dict[str, Any]:
    cls_res = client.post(
        "/api/v1/classes", json={"name": "12A6 Paper+LAN", "academic_year": "2026-2027"}, headers=hdrs
    )
    assert cls_res.status_code == 201
    cls_id = cls_res.json()["id"]

    st1 = client.post(
        f"/api/v1/classes/{cls_id}/students",
        json={"roster_code": "HS0001", "full_name": "Nguyễn Online"},
        headers=hdrs,
    ).json()
    st2 = client.post(
        f"/api/v1/classes/{cls_id}/students",
        json={"roster_code": "HS0002", "full_name": "Trần Thi Giấy"},
        headers=hdrs,
    ).json()

    ex_res = client.post(
        "/api/v1/exams",
        json={
            "classroom_id": cls_id,
            "title": "Kiểm tra P6 Paper & LAN",
            "duration_s": 900,
            "question_version_ids": qvids,
            "shuffle_questions": True,
            "shuffle_options": True,
            "seed": 202611,
            "open_waiting": True,
        },
        headers=hdrs,
    )
    assert ex_res.status_code == 201
    body = ex_res.json()
    invites = {inv["roster_code"]: inv["invite_code"] for inv in body["invites"]}
    return {"cls_id": cls_id, "exam": body["exam"], "st1": st1, "st2": st2, "invites": invites}


def test_paper_versions_booklet_pdf_and_omr_sheet_pdf(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "ExamGuardData"))
    with TestClient(app) as client:
        hdrs = _teacher_headers(client)
        seeded = _seed_rich_questions(client)
        ctx = _setup_two_student_class_and_exam(client, hdrs, [q["qvid"] for q in seeded])
        exam_id = ctx["exam"]["exam_id"]

        gen1 = client.post(
            f"/api/v1/paper/exams/{exam_id}/versions",
            json={"count": 4, "start_code": 101},
            headers=hdrs,
        )
        assert gen1.status_code == 200
        versions = gen1.json()["versions"]
        assert [v["version_code"] for v in versions] == ["101", "102", "103", "104"]
        assert all(v["question_count"] == 4 for v in versions)
        # Verify deterministic idempotency on repeat call
        gen2 = client.post(
            f"/api/v1/paper/exams/{exam_id}/versions",
            json={"count": 4, "start_code": 101},
            headers=hdrs,
        )
        assert gen2.status_code == 200
        assert gen2.json()["versions"] == versions

        # Booklet PDF (offline A4 fonts, math fallback, image embed, master answer table)
        pdf_res = client.get(f"/api/v1/paper/exams/{exam_id}/booklet.pdf", headers=hdrs)
        assert pdf_res.status_code == 200
        assert pdf_res.content.startswith(b"%PDF-")
        reader = pypdf.PdfReader(io.BytesIO(pdf_res.content))
        assert len(reader.pages) >= 5  # 4 versions + teacher answer key page
        full_text = "\n".join(p.extract_text() or "" for p in reader.pages)
        assert "101" in full_text and "104" in full_text
        assert "(1)/(2)" in full_text
        assert "BẢNG ĐÁP ÁN DÀNH CHO GIÁO VIÊN" in full_text

        # OMR A4 sheet PDF + PNG
        omr_pdf = client.get(f"/api/v1/paper/exams/{exam_id}/omr-sheet.pdf", headers=hdrs)
        assert omr_pdf.status_code == 200
        assert omr_pdf.content.startswith(b"%PDF-")
        omr_reader = pypdf.PdfReader(io.BytesIO(omr_pdf.content))
        omr_txt = omr_reader.pages[0].extract_text() or ""
        assert "PHIẾU TRẢ LỜI TRẮC NGHIỆM (OMR)" in omr_txt

        omr_png = client.get(f"/api/v1/paper/exams/{exam_id}/omr-sheet.pdf?fmt=png", headers=hdrs)
        assert omr_png.status_code == 200
        assert omr_png.content.startswith(b"\x89PNG")


def test_omr_rectification_ambiguity_detection_and_shared_grade_bridge(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "ExamGuardData"))
    with TestClient(app) as client:
        hdrs = _teacher_headers(client)
        seeded = _seed_rich_questions(client)
        ctx = _setup_two_student_class_and_exam(client, hdrs, [q["qvid"] for q in seeded])
        exam_id = ctx["exam"]["exam_id"]
        room_code = ctx["exam"]["room_code"]

        gen = client.post(
            f"/api/v1/paper/exams/{exam_id}/versions",
            json={"count": 3, "start_code": 101},
            headers=hdrs,
        ).json()
        pv102 = next(v for v in gen["versions"] if v["version_code"] == "102")
        perfect_102 = {int(q): [letters[0]] for q, letters in pv102["answer_key_map"].items()}

        # HS0001 joins and completes exam online via LAN (score = 5.0: 2 correct out of 4)
        j1_res = client.post(
            f"/api/v1/room/{room_code}/join",
            json={
                "roster_code": "HS0001",
                "invite_code": ctx["invites"]["HS0001"],
                "browser_key": "browser-key-hs0001",
            },
        )
        assert j1_res.status_code == 200
        j1 = j1_res.json()
        att1_id = j1["attempt"]["attempt_id"]
        assert client.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=hdrs).status_code == 200
        assert client.post(f"/api/v1/exams/{exam_id}/start", headers=hdrs).status_code == 200
        s1_hdrs = {"Authorization": f"Bearer {j1['attempt_token']}"}
        paper1 = client.get("/api/v1/attempts/me/paper", headers=s1_hdrs).json()
        for rev_i, q in enumerate(paper1["questions"], start=1):
            # Answer first 2 questions correctly, last 2 wrong
            target = next(s["opt_a"] for s in seeded if s["qvid"] == q["question_version_id"])
            if rev_i > 2:
                target = next(o["option_id"] for o in q["options"] if o["option_id"] != target)
            r_save = client.post(
                f"/api/v1/attempts/{att1_id}/answers",
                json={
                    "question_version_id": q["question_version_id"],
                    "selected_option_ids": [target],
                    "idempotency_key": f"omr-ol-{rev_i}-key",
                },
                headers=s1_hdrs,
            )
            assert r_save.status_code == 200
        assert client.post(f"/api/v1/attempts/{att1_id}/submit", headers=s1_hdrs).status_code == 200
        assert (
            client.post(
                f"/api/v1/exams/{exam_id}/close",
                json={"reason": "Kết thúc thu bài trực tuyến + chờ bài giấy"},
                headers=hdrs,
            ).status_code
            == 200
        )

        # Scan A for HS0002 (Paper 102): tilted + shadowed image!
        raw_png = render_omr_template_png(
            exam_title=ctx["exam"]["title"],
            classroom_name="12A6 Paper+LAN",
            question_count=4,
            filled_sbd="0002",
            filled_version="102",
            filled_answers=perfect_102,
        )
        # Apply realistic camera tilt (+5.5 deg rotation) + mild darkening shadow
        im_orig = Image.open(io.BytesIO(raw_png))
        im_tilted = im_orig.rotate(5.5, expand=True, fillcolor=(248, 248, 248))
        im_tilted = ImageEnhance.Brightness(im_tilted).enhance(0.86)
        tilted_buf = io.BytesIO()
        im_tilted.save(tilted_buf, format="PNG")
        tilted_bytes = tilted_buf.getvalue()

        up_a = client.post(
            f"/api/v1/paper/exams/{exam_id}/scans",
            files={"file": ("hs002_tilted.png", tilted_bytes, "image/png")},
            headers=hdrs,
        )
        assert up_a.status_code == 201
        scan_a = up_a.json()
        assert scan_a["status"] == "NEEDS_REVIEW"
        assert scan_a["confidence"]["fiducial_found"] is True
        assert scan_a["roster_code_detected"] == "0002"
        assert scan_a["student_id"] == ctx["st2"]["id"]
        assert scan_a["version_code_detected"] == "102"
        assert scan_a["version_code"] == "102"
        for q_no, expected_letters in pv102["answer_key_map"].items():
            assert scan_a["detected_answers"][q_no] == expected_letters[0]

        # Immutable original scan bytes preserved & downloadable
        orig_img_res = client.get(f"/api/v1/paper/scans/{scan_a['scan_id']}/image", headers=hdrs)
        assert orig_img_res.status_code == 200
        assert hashlib.sha256(orig_img_res.content).hexdigest() == scan_a["source_sha256"]

        # Scan B: Double mark on Q1 and faint pencil mark on Q2 -> MUST flag ambiguity!
        bad_answers = dict(perfect_102)
        bad_answers[1] = ["A", "B"]
        bad_png = render_omr_template_png(
            exam_title=ctx["exam"]["title"],
            classroom_name="12A6 Paper+LAN",
            question_count=4,
            filled_sbd="0002",
            filled_version="102",
            filled_answers=bad_answers,
            faint_answers={2},
        )
        up_b = client.post(
            f"/api/v1/paper/exams/{exam_id}/scans",
            files={"file": ("ambiguous.png", bad_png, "image/png")},
            headers=hdrs,
        )
        assert up_b.status_code == 201
        scan_b = up_b.json()
        flags_b = scan_b["ambiguous_flags"]
        assert "Q1_AMBIGUOUS" in flags_b
        assert "Q2_FAINT" in flags_b

        # Teacher overriding an ambiguous detected answer without >= 3 char reason MUST be rejected (400)
        override_answers = dict(scan_b["detected_answers"])
        override_answers["1"] = "D" if override_answers.get("1") != "D" else "C"
        bad_override = client.post(
            f"/api/v1/paper/scans/{scan_b['scan_id']}/confirm",
            json={
                "student_id": ctx["st2"]["id"],
                "version_code": "102",
                "confirmed_answers": override_answers,
                "reason": "  ",
            },
            headers=hdrs,
        )
        assert bad_override.status_code == 400

        # Scan C: Cropped missing fiducial corners -> MUST flag FIDUCIAL_NOT_FOUND with 0.0 confidence
        cropped = im_orig.crop((140, 140, 1060, 1540))
        crop_buf = io.BytesIO()
        cropped.save(crop_buf, format="PNG")
        up_c = client.post(
            f"/api/v1/paper/exams/{exam_id}/scans",
            files={"file": ("cropped.png", crop_buf.getvalue(), "image/png")},
            headers=hdrs,
        )
        assert up_c.status_code == 201
        assert "FIDUCIAL_NOT_FOUND" in up_c.json()["ambiguous_flags"]
        assert up_c.json()["overall_confidence"] == 0.0

        # Guard: attempting to overwrite HS0001 (who has online submission) with OMR -> 409 Conflict
        conflict_res = client.post(
            f"/api/v1/paper/scans/{scan_a['scan_id']}/confirm",
            json={
                "student_id": ctx["st1"]["id"],
                "version_code": "102",
                "confirmed_answers": scan_a["detected_answers"],
                "reason": "Thử gán nhầm vào học sinh đã thi online",
            },
            headers=hdrs,
        )
        assert conflict_res.status_code == 409

        # Confirm Scan A for HS0002 -> links Submission + automatically bridges to ScoreVersion!
        confirm_res = client.post(
            f"/api/v1/paper/scans/{scan_a['scan_id']}/confirm",
            json={
                "student_id": ctx["st2"]["id"],
                "version_code": "102",
                "confirmed_answers": scan_a["detected_answers"],
                "reason": "Xác nhận bài thi giấy Mã đề 102 chuẩn 10/10",
            },
            headers=hdrs,
        )
        assert confirm_res.status_code == 200
        assert confirm_res.json()["status"] == "CONFIRMED"
        assert confirm_res.json()["regraded"] is True

        # Shared Results Overview shows BOTH Online (5.0) & Paper OMR (10.0) seamlessly!
        ov = client.get(f"/api/v1/results/exams/{exam_id}", headers=hdrs).json()
        by_code = {s["roster_code"]: s for s in ov["students"]}
        assert by_code["HS0001"]["score_10"] == 5.0
        assert by_code["HS0002"]["score_10"] == 10.0
        assert "OMR" in by_code["HS0002"]["status_label"]
        assert ov["stats"]["mean_score"] == 7.5

        # Phúc khảo trace works cleanly on Paper OMR submission including PaperVersion permutation
        trace = client.get(
            f"/api/v1/results/exams/{exam_id}/students/{ctx['st2']['id']}/trace", headers=hdrs
        ).json()
        assert trace["submission"]["submission_mode"] == "paper_omr_confirmed"
        assert len(trace["questions"]) == 4
        assert all(q["is_correct"] for q in trace["questions"])

        # Verify DB persisted scan count
        session_factory = app.state.session_factory  # type: ignore[attr-defined]
        with session_factory() as db:
            scans_in_db = db.query(OmrScanSubmission).count()
            assert scans_in_db == 3


def test_pdf_two_column_vector_low_text_and_xlsx_profiles_benchmark(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "ExamGuardData"))
    with TestClient(app) as client:
        hdrs = _teacher_headers(client)
        font_reg, _font_bold = ensure_pdf_fonts()

        # 1. Synthetic 2-column Vietnamese PDF + vector lines (> 10 primitives) + end KEY block
        pdf_buf = io.BytesIO()
        c = rl_canvas.Canvas(pdf_buf, pagesize=(595.27, 841.89))
        c.setFont(font_reg, 11)
        # Left column (x=50)
        c.drawString(50, 780, "Câu 1: Thủ đô Việt Nam là thành phố nào?")
        c.drawString(50, 760, "A. Hà Nội")
        c.drawString(50, 740, "B. Huế")
        c.drawString(50, 720, "C. Đà Nẵng")
        c.drawString(50, 700, "D. Cần Thơ")
        # Right column (x=320) overlapping in y
        c.drawString(320, 780, "Câu 2: Giá trị của 3 x 4 bằng bao nhiêu?")
        c.drawString(320, 760, "A. 7")
        c.drawString(320, 740, "B. 12")
        c.drawString(320, 720, "C. 14")
        c.drawString(320, 700, "D. 16")
        # Key below right column
        c.drawString(320, 660, "KEY: 1.A 2.B")
        # Draw > 10 vector primitives (simulating geometric diagram)
        for i in range(12):
            c.line(50, 500 - i * 8, 180, 500 - i * 8)
        c.save()

        t0 = time.perf_counter()
        res_pdf = client.post(
            "/api/v1/questions/import",
            files={"file": ("two_col_vector.pdf", pdf_buf.getvalue(), "application/pdf")},
            headers=hdrs,
        )
        pdf_elapsed = time.perf_counter() - t0
        assert res_pdf.status_code == 201
        assert pdf_elapsed < 2.0
        job_pdf = res_pdf.json()
        assert job_pdf["parser_version"] == "pdf-v1.0"
        assert job_pdf["summary"]["diagnostics"]["two_column_pages"] == [1]
        assert job_pdf["summary"]["diagnostics"]["vector_diagram_pages"] == [1]
        drafts = job_pdf["drafts"]
        assert len(drafts) == 2
        assert "Thủ đô Việt Nam" in drafts[0]["blocks"][0]["text"]
        assert "3 x 4" in drafts[1]["blocks"][0]["text"]
        assert len(drafts[0]["answer"]["correct_option_ids"]) == 1
        assert len(drafts[1]["answer"]["correct_option_ids"]) == 1
        assert "PDF_VECTOR_OR_COMPLEX_LAYOUT" in drafts[0]["warnings"]

        # 2. Low-text / image-only PDF scan guard -> honest OCR-needed warning + raster image extraction
        scan_pdf = io.BytesIO()
        scan_img_buf = io.BytesIO()
        Image.new("RGB", (64, 48), color=(220, 230, 240)).save(scan_img_buf, format="PNG")
        scan_img_buf.seek(0)
        c2 = rl_canvas.Canvas(scan_pdf, pagesize=(595.27, 841.89))
        c2.drawImage(ImageReader(scan_img_buf), 60, 600, width=120, height=90)
        c2.save()
        res_scan_pdf = client.post(
            "/api/v1/questions/import",
            files={"file": ("scanned_blank.pdf", scan_pdf.getvalue(), "application/pdf")},
            headers=hdrs,
        )
        assert res_scan_pdf.status_code == 201
        diag_scan = res_scan_pdf.json()["summary"]["diagnostics"]
        assert diag_scan["low_text_pages"] == [1]
        assert diag_scan["extracted_images"] >= 1

        # 3. XLSX variants (vn_standard + missing key non-guessing + positional_abcd without header)
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["STT", "Câu hỏi", "A", "B", "C", "D", "Đáp án đúng"])
        ws.append([1, "Nước sôi ở nhiệt độ bao nhiêu độ C?", "50", "80", "100", "120", "C"])
        ws.append([2, "Kim loại nào dẫn điện tốt nhất?", "Sắt", "Bạc", "Nhôm", "Chì", ""])
        xlsx_buf = io.BytesIO()
        wb.save(xlsx_buf)

        res_xlsx = client.post(
            "/api/v1/questions/import",
            data={"profile": "vn_standard"},
            files={
                "file": (
                    "bank_vn.xlsx",
                    xlsx_buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=hdrs,
        )
        assert res_xlsx.status_code == 201
        d_xl = res_xlsx.json()["drafts"]
        assert len(d_xl) == 2
        assert len(d_xl[0]["answer"]["correct_option_ids"]) == 1
        # Row 2 had blank key -> MUST NOT guess answer!
        assert d_xl[1]["answer"]["status"] == "unknown"
        assert "ANSWER_NOT_FOUND" in d_xl[1]["warnings"]

        # Positional XLSX without header row
        wb2 = openpyxl.Workbook()
        ws2 = wb2.active
        assert ws2 is not None
        ws2.append(["Câu hỏi vị trí không tiêu đề?", "Sai 1", "Đúng 2", "Sai 3", "Sai 4", "B"])
        xl2_buf = io.BytesIO()
        wb2.save(xl2_buf)
        res_pos = client.post(
            "/api/v1/questions/import",
            data={"profile": "positional_abcd"},
            files={
                "file": (
                    "positional.xlsx",
                    xl2_buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=hdrs,
        )
        assert res_pos.status_code == 201
        assert len(res_pos.json()["drafts"]) == 1
        assert res_pos.json()["drafts"][0]["answer"]["status"] == "confirmed"
