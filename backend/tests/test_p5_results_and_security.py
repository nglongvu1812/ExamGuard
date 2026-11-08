"""P5 tests: pure scoring, publish gates, isolation, regrade supersession, receipts, XLSX, Phúc khảo."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from pathlib import Path
from typing import Any

import openpyxl
from app.core.config import Settings
from app.db.models import (
    AnswerKeyVersion,
    AuditEvent,
    GradeRun,
    Question,
    QuestionVersion,
    ReceiptVersion,
    ScoreVersion,
)
from app.main import create_app
from app.services.export_service import (
    mask_roster_code,
    mask_student_name,
    neutralize_excel_formula,
    render_share_card_png_bytes,
)
from app.services.grading_service import QuestionScoringSpec, score_submission_answers
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select


def _teacher_headers(client: TestClient) -> dict[str, str]:
    res = client.post("/api/v1/auth/teacher/local-session")
    assert res.status_code == 200
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_two_questions(client: TestClient) -> list[dict[str, Any]]:
    app = client.app
    session_factory = app.state.session_factory  # type: ignore[attr-defined]
    seeded: list[dict[str, Any]] = []
    with session_factory() as db:
        for idx in range(1, 3):
            qid = str(uuid.uuid4())
            qvid = str(uuid.uuid4())
            opt_a = str(uuid.uuid4())
            opt_b = str(uuid.uuid4())
            opt_c = str(uuid.uuid4())
            q = Question(id=qid, bank_name="Toán P5", active_version_id=qvid)
            qv = QuestionVersion(
                id=qvid,
                question_id=qid,
                version_number=1,
                content_blocks_json=json.dumps([{"type": "text", "text": f"Câu hỏi số {idx}"}]),
                options_json=json.dumps(
                    [
                        {
                            "option_id": opt_a,
                            "label": "A",
                            "blocks": [{"type": "text", "text": f"Đáp án A câu {idx}"}],
                        },
                        {
                            "option_id": opt_b,
                            "label": "B",
                            "blocks": [{"type": "text", "text": f"Đáp án B câu {idx}"}],
                        },
                        {
                            "option_id": opt_c,
                            "label": "C",
                            "blocks": [{"type": "text", "text": f"Đáp án C câu {idx}"}],
                        },
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
                correct_option_ids_json=json.dumps([opt_a]),
                reason="Đáp án ban đầu",
                approved_by=1,
            )
            db.add(q)
            db.flush()
            db.add(qv)
            db.flush()
            db.add(kv)
            db.flush()
            seeded.append({"qvid": qvid, "opt_a": opt_a, "opt_b": opt_b, "opt_c": opt_c})
        db.commit()
    return seeded


def _setup_completed_exam_context(
    client: TestClient,
    *,
    student_specs: list[tuple[str, str]],
) -> dict[str, Any]:
    headers = _teacher_headers(client)
    cls_res = client.post(
        "/api/v1/classes",
        json={"name": "12A-P5", "academic_year": "2026-2027"},
        headers=headers,
    )
    assert cls_res.status_code == 201
    cls_id = cls_res.json()["id"]

    students_by_code: dict[str, str] = {}
    for code, name in student_specs:
        st_res = client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": code, "full_name": name},
            headers=headers,
        )
        assert st_res.status_code == 201
        students_by_code[code] = st_res.json()["id"]

    q_items = _seed_two_questions(client)
    exam_res = client.post(
        "/api/v1/exams",
        json={
            "classroom_id": cls_id,
            "title": "Kiểm tra cuối kỳ Tiếng Việt",
            "duration_s": 900,
            "question_version_ids": [q["qvid"] for q in q_items],
            "shuffle_questions": True,
            "shuffle_options": True,
            "seed": 2026,
            "open_waiting": True,
        },
        headers=headers,
    )
    assert exam_res.status_code == 201
    exam_id = exam_res.json()["exam"]["exam_id"]
    room_code = exam_res.json()["exam"]["room_code"]
    invites = {inv["roster_code"]: inv["invite_code"] for inv in exam_res.json()["invites"]}
    return {
        "headers": headers,
        "cls_id": cls_id,
        "exam_id": exam_id,
        "room_code": room_code,
        "invites": invites,
        "students_by_code": students_by_code,
        "questions": q_items,
    }


def _join_and_approve(
    client: TestClient,
    headers: dict[str, str],
    exam_id: str,
    room_code: str,
    roster_code: str,
    invite_code: str,
    browser_key: str,
) -> tuple[str, str]:
    j = client.post(
        f"/api/v1/room/{room_code}/join",
        json={"roster_code": roster_code, "invite_code": invite_code, "browser_key": browser_key},
    )
    assert j.status_code == 200
    token = j.json()["attempt_token"]
    att_id = j.json()["attempt"]["attempt_id"]
    app_res = client.post(f"/api/v1/rooms/{exam_id}/attempts/{att_id}/approve", headers=headers)
    assert app_res.status_code == 200
    return token, att_id


def test_pure_scoring_engine_unit() -> None:
    specs = [
        QuestionScoringSpec("q1", position=1, weight=1.0, correct_option_ids=("a1",)),
        QuestionScoringSpec("q2", position=2, weight=2.0, correct_option_ids=("b2",)),
        QuestionScoringSpec("q3", position=3, weight=1.0, correct_option_ids=("c1", "c2")),
    ]

    full_outcome = score_submission_answers(
        {"q1": ["a1"], "q2": ["b2"], "q3": ["c2", "c1"]},
        specs,
    )
    assert full_outcome.raw_correct == 3
    assert full_outcome.total_questions == 3
    assert full_outcome.max_points == 4.0
    assert full_outcome.earned_points == 4.0
    assert full_outcome.score_10 == 10.0

    partial_outcome = score_submission_answers(
        {"q1": ["a1"], "q2": ["wrong"], "q3": ["c1"]},
        specs,
    )
    assert partial_outcome.raw_correct == 1
    assert partial_outcome.earned_points == 1.0
    assert partial_outcome.score_10 == 2.5

    empty_outcome = score_submission_answers({}, specs)
    assert empty_outcome.raw_correct == 0
    assert empty_outcome.score_10 == 0.0


def test_results_security_gates_publish_and_receipts(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "ExamGuardData")
    app = create_app(settings)
    with TestClient(app) as client:
        ctx = _setup_completed_exam_context(
            client,
            student_specs=[("HS001", "Nguyễn Văn An"), ("HS002", "Trần Thị Bình")],
        )
        headers = ctx["headers"]
        exam_id = ctx["exam_id"]
        room_code = ctx["room_code"]
        q1, q2 = ctx["questions"]

        tok1, att1 = _join_and_approve(
            client, headers, exam_id, room_code, "HS001", ctx["invites"]["HS001"], "device-hs1-key"
        )
        tok2, att2 = _join_and_approve(
            client, headers, exam_id, room_code, "HS002", ctx["invites"]["HS002"], "device-hs2-key"
        )
        s1_hdr = {"Authorization": f"Bearer {tok1}"}
        s2_hdr = {"Authorization": f"Bearer {tok2}"}

        # 1. Zero disclosure in WAITING
        assert client.get("/api/v1/attempts/me/result", headers=s1_hdr).status_code == 403
        assert client.get("/api/v1/attempts/me/receipt.pdf", headers=s1_hdr).status_code == 403
        assert client.post(
            f"/api/v1/results/exams/{exam_id}/publish",
            json={"confirm": True},
            headers=headers,
        ).status_code == 409

        # Start exam & answer: HS1 gets 2/2, HS2 gets 1/2 (picks q2.opt_b)
        assert client.post(f"/api/v1/exams/{exam_id}/start", headers=headers).status_code == 200
        assert client.get("/api/v1/attempts/me/result", headers=s1_hdr).status_code == 403

        for idx, (hdr, att_id, ans2) in enumerate(
            [(s1_hdr, att1, q2["opt_a"]), (s2_hdr, att2, q2["opt_b"])], start=1
        ):
            r1 = client.post(
                f"/api/v1/attempts/{att_id}/answers",
                json={
                    "question_version_id": q1["qvid"],
                    "selected_option_ids": [q1["opt_a"]],
                    "idempotency_key": f"k1-{idx}",
                },
                headers=hdr,
            )
            r2 = client.post(
                f"/api/v1/attempts/{att_id}/answers",
                json={
                    "question_version_id": q2["qvid"],
                    "selected_option_ids": [ans2],
                    "idempotency_key": f"k2-{idx}",
                },
                headers=hdr,
            )
            assert r1.status_code == 200 and r2.status_code == 200
            assert client.post(f"/api/v1/attempts/{att_id}/submit", headers=hdr).status_code == 200

        # Still FORBIDDEN in RUNNING and CLOSED and REVIEWED
        assert client.post(
            f"/api/v1/exams/{exam_id}/close",
            json={"reason": "Hết giờ làm bài"},
            headers=headers,
        ).status_code == 200
        for forbidden_url in (
            "/api/v1/attempts/me/result",
            "/api/v1/attempts/me/receipt.pdf",
            "/api/v1/attempts/me/share-card.png",
        ):
            res_closed = client.get(forbidden_url, headers=s1_hdr)
            assert res_closed.status_code == 403
            assert q1["opt_a"] not in res_closed.text

        # Gate check: cannot publish directly from CLOSED without REVIEWED
        assert client.post(
            f"/api/v1/results/exams/{exam_id}/publish",
            json={"confirm": True},
            headers=headers,
        ).status_code == 409

        # Review exam -> REVIEWED
        rev_res = client.post(
            f"/api/v1/results/exams/{exam_id}/review",
            json={"reason": "Đã kiểm tra bài nộp"},
            headers=headers,
        )
        assert rev_res.status_code == 200
        assert rev_res.json()["status"] == "REVIEWED"

        # Still FORBIDDEN in REVIEWED before PUBLISH!
        assert client.get("/api/v1/attempts/me/result", headers=s1_hdr).status_code == 403

        # Publish exam -> PUBLISHED
        pub_res = client.post(
            f"/api/v1/results/exams/{exam_id}/publish",
            json={"confirm": True},
            headers=headers,
        )
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "PUBLISHED"
        assert pub_res.json()["receipts_issued"] == 2

        # Cross-student isolation even AFTER publish
        assert client.get(f"/api/v1/attempts/{att2}/result", headers=s1_hdr).status_code == 403

        # HS1 gets full published result + PDF + masked PNG
        s1_result = client.get("/api/v1/attempts/me/result", headers=s1_hdr)
        assert s1_result.status_code == 200
        body1 = s1_result.json()
        assert body1["score_10"] == 10.0
        assert body1["raw_correct"] == 2
        assert body1["receipt_version"] == 1
        assert body1["superseded_previous"] is False

        pdf_res = client.get("/api/v1/attempts/me/receipt.pdf", headers=s1_hdr)
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"].startswith("application/pdf")
        assert pdf_res.content.startswith(b"%PDF-")

        png_res = client.get("/api/v1/attempts/me/share-card.png", headers=s1_hdr)
        assert png_res.status_code == 200
        assert png_res.headers["content-type"].startswith("image/png")
        img = Image.open(io.BytesIO(png_res.content))
        assert img.size == (900, 480)

        # Verify masking removes raw full PII from share-card generator helper
        assert mask_student_name("Nguyễn Văn An") == "Ng*** A***"
        assert mask_roster_code("HS001") == "HS***01"


def test_regrade_after_publish_supersedes_scores_and_receipts_and_audit(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "ExamGuardData")
    app = create_app(settings)
    with TestClient(app) as client:
        ctx = _setup_completed_exam_context(
            client,
            student_specs=[("HS001", "Lê Văn Một"), ("HS002", "Phạm Thị Hai")],
        )
        headers = ctx["headers"]
        exam_id = ctx["exam_id"]
        room_code = ctx["room_code"]
        q1, q2 = ctx["questions"]

        tok1, att1 = _join_and_approve(
            client, headers, exam_id, room_code, "HS001", ctx["invites"]["HS001"], "dev-regrade-1"
        )
        tok2, att2 = _join_and_approve(
            client, headers, exam_id, room_code, "HS002", ctx["invites"]["HS002"], "dev-regrade-2"
        )
        s1_hdr = {"Authorization": f"Bearer {tok1}"}
        s2_hdr = {"Authorization": f"Bearer {tok2}"}

        assert client.post(f"/api/v1/exams/{exam_id}/start", headers=headers).status_code == 200
        # HS1 answers A/A -> initially 10.0; HS2 answers A/B -> initially 5.0
        for idx, (hdr, att_id, ans2) in enumerate(
            [(s1_hdr, att1, q2["opt_a"]), (s2_hdr, att2, q2["opt_b"])], start=1
        ):
            r1 = client.post(
                f"/api/v1/attempts/{att_id}/answers",
                json={
                    "question_version_id": q1["qvid"],
                    "selected_option_ids": [q1["opt_a"]],
                    "idempotency_key": f"regrade-q1-{idx}",
                },
                headers=hdr,
            )
            r2 = client.post(
                f"/api/v1/attempts/{att_id}/answers",
                json={
                    "question_version_id": q2["qvid"],
                    "selected_option_ids": [ans2],
                    "idempotency_key": f"regrade-q2-{idx}",
                },
                headers=hdr,
            )
            assert r1.status_code == 200 and r2.status_code == 200
            assert client.post(f"/api/v1/attempts/{att_id}/submit", headers=hdr).status_code == 200

        client.post(f"/api/v1/exams/{exam_id}/close", json={"reason": "Đóng"}, headers=headers)
        client.post(f"/api/v1/results/exams/{exam_id}/review", json={"reason": "Duyệt"}, headers=headers)
        client.post(f"/api/v1/results/exams/{exam_id}/publish", json={"confirm": True}, headers=headers)

        # Reject key update without valid reason
        bad_regrade = client.post(
            f"/api/v1/results/exams/{exam_id}/grade",
            json={"reason": "  ", "updated_keys": {q2["qvid"]: [q2["opt_b"]]}},
            headers=headers,
        )
        assert bad_regrade.status_code == 400

        # Valid key change + regrade after publish
        regrade_res = client.post(
            f"/api/v1/results/exams/{exam_id}/grade",
            json={
                "reason": "Điều chỉnh đáp án câu 2 thành B theo tổ bộ môn",
                "updated_keys": {q2["qvid"]: [q2["opt_b"]]},
            },
            headers=headers,
        )
        assert regrade_res.status_code == 200
        rg = regrade_res.json()
        assert rg["run_number"] == 2
        assert rg["receipts_updated"] == 2

        # HS2 should now see 10.0 and superseded_previous banner!
        hs2_res = client.get("/api/v1/attempts/me/result", headers=s2_hdr)
        assert hs2_res.status_code == 200
        body2 = hs2_res.json()
        assert body2["score_10"] == 10.0
        assert body2["score_version"] == 2
        assert body2["receipt_version"] == 2
        assert body2["superseded_previous"] is True
        assert "Điều chỉnh đáp án câu 2" in (body2["regrade_reason"] or "")

        # Verify immutable DB chains: v1 preserved alongside v2
        session_factory = app.state.session_factory  # type: ignore[attr-defined]
        with session_factory() as db:
            runs = db.execute(select(GradeRun).where(GradeRun.exam_id == exam_id)).scalars().all()
            assert len(runs) == 2

            svs = (
                db.execute(
                    select(ScoreVersion)
                    .where(
                        ScoreVersion.exam_id == exam_id,
                        ScoreVersion.student_id == ctx["students_by_code"]["HS002"],
                    )
                    .order_by(ScoreVersion.version.asc())
                )
                .scalars()
                .all()
            )
            assert len(svs) == 2
            assert svs[0].is_current is False and svs[0].score_10 == 5.0
            assert svs[1].is_current is True and svs[1].supersedes_id == svs[0].id

            rvs = (
                db.execute(
                    select(ReceiptVersion)
                    .where(
                        ReceiptVersion.exam_id == exam_id,
                        ReceiptVersion.student_id == ctx["students_by_code"]["HS002"],
                    )
                    .order_by(ReceiptVersion.version.asc())
                )
                .scalars()
                .all()
            )
            assert len(rvs) == 2
            assert rvs[0].is_current is False
            assert rvs[1].is_current is True and rvs[1].supersedes_id == rvs[0].id

        # Audit chain valid!
        audit_res = client.get("/api/v1/audit/verify", headers=headers)
        assert audit_res.status_code == 200
        assert audit_res.json()["valid"] is True
        actions = [e["action"] for e in audit_res.json()["recent_events"]]
        assert "UPDATE_ANSWER_KEY" in actions
        assert "REGRADE_AFTER_PUBLISH" in actions

        # Tampering with an AuditEvent directly breaks verify_audit_chain
        with session_factory() as db:
            ev = db.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)).scalar_one()
            ev.details_json = '{"tampered": true}'
            db.commit()
        tampered_res = client.get("/api/v1/audit/verify", headers=headers)
        assert tampered_res.status_code == 200
        assert tampered_res.json()["valid"] is False


def test_excel_formula_injection_stats_and_phuc_khao_trace(tmp_path: Path) -> None:
    assert neutralize_excel_formula("=CMD|'/C calc'!A0") == "'=CMD|'/C calc'!A0"
    assert neutralize_excel_formula("  +SUM(1,2)") == "'  +SUM(1,2)"
    assert neutralize_excel_formula("Nguyễn Văn A") == "Nguyễn Văn A"

    settings = Settings(data_dir=tmp_path / "ExamGuardData")
    app = create_app(settings)
    with TestClient(app) as client:
        ctx = _setup_completed_exam_context(
            client,
            student_specs=[
                ("=HS01", "=CMD|'/C calc'!A0"),
                ("HS002", "+SUM(1,2)"),
                ("HS003", "Vắng mặt"),
            ],
        )
        headers = ctx["headers"]
        exam_id = ctx["exam_id"]
        room_code = ctx["room_code"]
        q1, q2 = ctx["questions"]

        tok1, att1 = _join_and_approve(
            client, headers, exam_id, room_code, "=HS01", ctx["invites"]["=HS01"], "dev-xlsx-1"
        )
        tok2, att2 = _join_and_approve(
            client, headers, exam_id, room_code, "HS002", ctx["invites"]["HS002"], "dev-xlsx-2"
        )
        s1_hdr = {"Authorization": f"Bearer {tok1}"}
        s2_hdr = {"Authorization": f"Bearer {tok2}"}

        assert client.post(f"/api/v1/exams/{exam_id}/start", headers=headers).status_code == 200
        # Student 1: 2/2 (10.0), Student 2: 0/2 (0.0), Student 3: NOT_JOINED
        r1 = client.post(
            f"/api/v1/attempts/{att1}/answers",
            json={
                "question_version_id": q1["qvid"],
                "selected_option_ids": [q1["opt_a"]],
                "idempotency_key": "xlsx-q1-1",
            },
            headers=s1_hdr,
        )
        r2 = client.post(
            f"/api/v1/attempts/{att1}/answers",
            json={
                "question_version_id": q2["qvid"],
                "selected_option_ids": [q2["opt_a"]],
                "idempotency_key": "xlsx-q2-1",
            },
            headers=s1_hdr,
        )
        assert r1.status_code == 200 and r2.status_code == 200
        assert client.post(f"/api/v1/attempts/{att1}/submit", headers=s1_hdr).status_code == 200

        r3 = client.post(
            f"/api/v1/attempts/{att2}/answers",
            json={
                "question_version_id": q1["qvid"],
                "selected_option_ids": [q1["opt_c"]],
                "idempotency_key": "xlsx-q1-2",
            },
            headers=s2_hdr,
        )
        assert r3.status_code == 200
        assert client.post(f"/api/v1/attempts/{att2}/submit", headers=s2_hdr).status_code == 200

        client.post(f"/api/v1/exams/{exam_id}/close", json={"reason": "Đóng"}, headers=headers)
        client.post(f"/api/v1/results/exams/{exam_id}/review", json={"reason": "Duyệt"}, headers=headers)
        client.post(f"/api/v1/results/exams/{exam_id}/publish", json={"confirm": True}, headers=headers)

        overview = client.get(f"/api/v1/results/exams/{exam_id}", headers=headers).json()
        assert overview["stats"]["mean_score"] == 5.0
        assert overview["stats"]["graded_count"] == 2
        assert overview["stats"]["unsubmitted_count"] == 1

        xlsx_res = client.get(f"/api/v1/results/exams/{exam_id}/export.xlsx", headers=headers)
        assert xlsx_res.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
        ws_grades = wb["Bảng điểm"]
        rows = list(ws_grades.iter_rows(values_only=True))
        codes_in_sheet = [r[1] for r in rows[1:]]
        names_in_sheet = [r[2] for r in rows[1:]]
        assert "'=HS01" in codes_in_sheet
        assert "'=CMD|'/C calc'!A0" in names_in_sheet
        assert "'+SUM(1,2)" in names_in_sheet

        ws_stats = wb["Thống kê"]
        stats_map = {r[0]: r[1] for r in ws_stats.iter_rows(values_only=True) if r[0]}
        assert stats_map["Tổng sĩ số"] == 3
        assert stats_map["Số bài đã chấm"] == 2
        assert stats_map["Chưa nộp / Chưa thi"] == 1
        assert stats_map["Điểm trung bình"] == 5.0

        # Check Phúc khảo trace
        st1_id = ctx["students_by_code"]["=HS01"]
        trace_res = client.get(
            f"/api/v1/results/exams/{exam_id}/students/{st1_id}/trace",
            headers=headers,
        )
        assert trace_res.status_code == 200
        trace = trace_res.json()
        assert trace["permutation_seed"] is not None
        assert len(trace["questions"]) == 2
        assert len(trace["answer_revisions"]) == 2
        assert len(trace["score_versions"]) == 1
        assert len(trace["receipt_versions"]) == 1
        assert trace["submission"]["snapshot_hash"]
        expected_sha = hashlib.sha256(b"check-sha").hexdigest()
        assert len(trace["submission"]["snapshot_hash"]) == len(expected_sha)

        # PNG share card utility direct assertion: full PII string not rendered cleanly
        png_bytes = render_share_card_png_bytes(
            exam_title="Kiểm tra giữa kỳ",
            score_10=9.5,
            raw_correct=19,
            total_questions=20,
            masked_name=mask_student_name("Nguyễn Văn Bình"),
            masked_code=mask_roster_code("HS099"),
            receipt_code="EG-ROOM1-HS099",
            receipt_version=1,
        )
        assert len(png_bytes) > 1000
