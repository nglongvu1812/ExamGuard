"""P3 Exam Engine tests: state machine, permutations, commit-before-ACK, server timer, crash recovery, backups."""

from __future__ import annotations

import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.db.models import AnswerRevision, Exam, Submission
from app.main import create_app
from app.services.backup_service import restore_backup_archive
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select


def _teacher_headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/v1/auth/teacher/local-session").json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_bank_with_n_questions(client: TestClient, headers: dict[str, str], n: int = 5) -> list[str]:
    doc = Document()
    key_tokens: list[str] = []
    for i in range(1, n + 1):
        doc.add_paragraph(f"Câu {i}: Giá trị của {i} + 1 là bao nhiêu?")
        doc.add_paragraph(f"A. {i}   B. {i + 1}   C. {i + 2}   D. {i + 3}")
        key_tokens.append(f"{i}B")
    doc.add_paragraph("ĐÁP ÁN: " + " ".join(key_tokens))

    buf = io.BytesIO()
    doc.save(buf)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    imp = client.post(
        "/api/v1/questions/import",
        files={"file": ("de_5_cau.docx", buf.getvalue(), mime)},
        headers=headers,
    )
    assert imp.status_code == 201
    job_id = imp.json()["job_id"]
    batch = client.post(f"/api/v1/questions/import/{job_id}/approve-ready", headers=headers)
    assert batch.status_code == 200
    assert batch.json()["approved_count"] == n

    bank = client.get("/api/v1/questions/bank", headers=headers).json()
    return [item["version_id"] for item in bank]


def test_exam_invalid_state_transitions_and_permutation_mapping(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        cls_id = client.post(
            "/api/v1/classes",
            json={"name": "12A5", "academic_year": "2026-2027"},
            headers=headers,
        ).json()["id"]
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS001", "full_name": "Nguyễn A"},
            headers=headers,
        )
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS002", "full_name": "Trần B"},
            headers=headers,
        )

        # Empty waiting room cannot transition directly to RUNNING
        empty_room = client.post(
            "/api/v1/rooms",
            json={"classroom_id": cls_id, "title": "Phòng rỗng", "duration_s": 600},
            headers=headers,
        ).json()["room"]["exam_id"]
        assert client.post(f"/api/v1/exams/{empty_room}/start", headers=headers).status_code == 400

        q_vids = _seed_bank_with_n_questions(client, headers, 5)
        created = client.post(
            "/api/v1/exams",
            json={
                "classroom_id": cls_id,
                "title": "Kiểm tra Toán",
                "duration_s": 900,
                "question_version_ids": q_vids,
                "shuffle_questions": True,
                "shuffle_options": True,
                "open_waiting": False,
            },
            headers=headers,
        )
        assert created.status_code == 201
        exam_id = created.json()["exam"]["exam_id"]

        # Invalid jump READY -> RUNNING before WAITING must be rejected (409)
        assert client.post(f"/api/v1/exams/{exam_id}/start", headers=headers).status_code == 409

        waiting = client.post(f"/api/v1/exams/{exam_id}/open-waiting", headers=headers)
        assert waiting.status_code == 200
        invites = {inv["roster_code"]: inv["invite_code"] for inv in waiting.json()["invites"]}
        room_code = waiting.json()["exam"]["room_code"]

        j1 = client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS001", "invite_code": invites["HS001"], "browser_key": "dev-hs001-key"},
        ).json()
        j2 = client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS002", "invite_code": invites["HS002"], "browser_key": "dev-hs002-key"},
        ).json()
        client.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=headers)

        # Cannot fetch paper while still WAITING
        pre_paper = client.get(
            "/api/v1/attempts/me/paper",
            headers={"Authorization": f"Bearer {j1['attempt_token']}"},
        )
        assert pre_paper.status_code == 403

        # Start exam -> fetch paper for both students
        started = client.post(f"/api/v1/exams/{exam_id}/start", headers=headers)
        assert started.status_code == 200
        assert started.json()["status"] == "RUNNING"

        p1 = client.get(
            "/api/v1/attempts/me/paper",
            headers={"Authorization": f"Bearer {j1['attempt_token']}"},
        ).json()
        p2 = client.get(
            "/api/v1/attempts/me/paper",
            headers={"Authorization": f"Bearer {j2['attempt_token']}"},
        ).json()
        assert len(p1["questions"]) == 5
        assert len(p2["questions"]) == 5
        # Verify option_id sets match authoritative bank even after permutation
        bank_opts = {
            item["version_id"]: {o["option_id"] for o in item["options"]}
            for item in client.get("/api/v1/questions/bank", headers=headers).json()
        }
        for q in p1["questions"]:
            assert {o["option_id"] for o in q["options"]} == bank_opts[q["question_version_id"]]

        # Close exam -> cannot transition CLOSED -> RUNNING (409)
        assert client.post(f"/api/v1/exams/{exam_id}/close", json={}, headers=headers).status_code == 200
        assert client.post(f"/api/v1/exams/{exam_id}/start", headers=headers).status_code == 409


def test_five_student_e2e_pause_resume_restart_and_no_key_leak(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    app = create_app(Settings(data_dir=data_dir))
    student_tokens: list[tuple[str, str]] = []
    exam_id = ""

    with TestClient(app) as client:
        headers = _teacher_headers(client)
        cls_id = client.post(
            "/api/v1/classes",
            json={"name": "12A6", "academic_year": "2026-2027"},
            headers=headers,
        ).json()["id"]
        for i in range(1, 6):
            client.post(
                f"/api/v1/classes/{cls_id}/students",
                json={"roster_code": f"HS00{i}", "full_name": f"Học sinh {i}"},
                headers=headers,
            )

        q_vids = _seed_bank_with_n_questions(client, headers, 5)
        created = client.post(
            "/api/v1/exams",
            json={
                "classroom_id": cls_id,
                "title": "Thi 5 HS",
                "duration_s": 600,
                "question_version_ids": q_vids,
                "shuffle_questions": True,
                "shuffle_options": True,
                "open_waiting": True,
            },
            headers=headers,
        ).json()
        exam_id = created["exam"]["exam_id"]
        room_code = created["exam"]["room_code"]
        invites = {inv["roster_code"]: inv["invite_code"] for inv in created["invites"]}

        for i in range(1, 6):
            code = f"HS00{i}"
            j = client.post(
                f"/api/v1/room/{room_code}/join",
                json={
                    "roster_code": code,
                    "invite_code": invites[code],
                    "browser_key": f"device-key-00{i}",
                },
            ).json()
            student_tokens.append((j["attempt"]["attempt_id"], j["attempt_token"]))

        client.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=headers)
        client.post(f"/api/v1/exams/{exam_id}/start", headers=headers)

        # Fetch paper for Student 1 & assert ZERO answer key leakage anywhere in payload
        att0_id, tok0 = student_tokens[0]
        paper_res = client.get("/api/v1/attempts/me/paper", headers={"Authorization": f"Bearer {tok0}"})
        assert paper_res.status_code == 200
        raw_paper_str = paper_res.text.lower()
        assert "correct_option_ids" not in raw_paper_str
        assert "answer_key" not in raw_paper_str
        assert "seed" not in paper_res.json()

        q0 = paper_res.json()["questions"][0]
        chosen_opt = q0["options"][0]["option_id"]

        # Save answer + replay same idempotency_key -> duplicate=True with same server_revision
        idem_key = str(uuid.uuid4())
        ack1 = client.post(
            f"/api/v1/attempts/{att0_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": [chosen_opt],
                "idempotency_key": idem_key,
                "client_timestamp": "2020-01-01T00:00:00Z",  # tampered client time does not break valid write
            },
            headers={"Authorization": f"Bearer {tok0}"},
        )
        assert ack1.status_code == 200
        assert ack1.json()["server_revision"] == 1
        assert ack1.json()["duplicate"] is False

        ack_replay = client.post(
            f"/api/v1/attempts/{att0_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": [chosen_opt],
                "idempotency_key": idem_key,
            },
            headers={"Authorization": f"Bearer {tok0}"},
        )
        assert ack_replay.status_code == 200
        assert ack_replay.json()["server_revision"] == 1
        assert ack_replay.json()["duplicate"] is True

        # Reject invalid option UUID belonging to another question
        bad_opt = client.post(
            f"/api/v1/attempts/{att0_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": ["non-existent-option-uuid"],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {tok0}"},
        )
        assert bad_opt.status_code == 400

        # Teacher pauses -> student writes rejected; resumes -> writes succeed again
        assert (
            client.post(
                f"/api/v1/exams/{exam_id}/pause",
                json={"reason": "Kiểm tra kết nối AP phòng thi"},
                headers=headers,
            ).status_code
            == 200
        )
        paused_save = client.post(
            f"/api/v1/attempts/{att0_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": [q0["options"][1]["option_id"]],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {tok0}"},
        )
        assert paused_save.status_code == 409
        assert client.post(f"/api/v1/exams/{exam_id}/resume", headers=headers).status_code == 200

        # Other 4 students save & submit cleanly
        for att_id, tok in student_tokens[1:]:
            p = client.get("/api/v1/attempts/me/paper", headers={"Authorization": f"Bearer {tok}"}).json()
            for q in p["questions"][:2]:
                client.post(
                    f"/api/v1/attempts/{att_id}/answers",
                    json={
                        "question_version_id": q["question_version_id"],
                        "selected_option_ids": [q["options"][0]["option_id"]],
                        "idempotency_key": str(uuid.uuid4()),
                    },
                    headers={"Authorization": f"Bearer {tok}"},
                )
            sub = client.post(
                f"/api/v1/attempts/{att_id}/submit",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert sub.status_code == 200
            assert sub.json()["already_submitted"] is False

    # SIMULATE CRASH / FULL SERVER RESTART with fresh app instance on same data_dir
    restarted_app = create_app(Settings(data_dir=data_dir))
    with TestClient(restarted_app) as restarted_client:
        att0_id, tok0 = student_tokens[0]
        sync = restarted_client.get(
            f"/api/v1/attempts/{att0_id}/sync",
            headers={"Authorization": f"Bearer {tok0}"},
        )
        assert sync.status_code == 200
        sync_json = sync.json()
        assert sync_json["latest_revision"] == 1
        assert len(sync_json["saved_answers"]) == 1

        # Simulate expired server deadline -> tampered client clock does NOT extend submission write
        with restarted_app.state.session_factory() as db:
            ex = db.get(Exam, exam_id)
            assert ex is not None
            ex.deadline_at = datetime.now(UTC) - timedelta(seconds=60)
            db.commit()

        q_id_saved = next(iter(sync_json["saved_answers"].keys()))
        expired_write = restarted_client.post(
            f"/api/v1/attempts/{att0_id}/answers",
            json={
                "question_version_id": q_id_saved,
                "selected_option_ids": [],
                "idempotency_key": str(uuid.uuid4()),
                "client_timestamp": "2020-01-01T00:00:00Z",  # clock set 6 years behind
            },
            headers={"Authorization": f"Bearer {tok0}"},
        )
        assert expired_write.status_code == 409


def test_concurrent_double_submit_and_close_race(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        cls_id = client.post(
            "/api/v1/classes",
            json={"name": "12A7", "academic_year": "2026-2027"},
            headers=headers,
        ).json()["id"]
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS010", "full_name": "Lê Dũng"},
            headers=headers,
        )
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS011", "full_name": "Phạm Em"},
            headers=headers,
        )

        q_vids = _seed_bank_with_n_questions(client, headers, 3)
        created = client.post(
            "/api/v1/exams",
            json={
                "classroom_id": cls_id,
                "title": "Race Test",
                "duration_s": 600,
                "question_version_ids": q_vids,
                "open_waiting": True,
            },
            headers=headers,
        ).json()
        exam_id = created["exam"]["exam_id"]
        room_code = created["exam"]["room_code"]
        invites = {inv["roster_code"]: inv["invite_code"] for inv in created["invites"]}

        j10 = client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS010", "invite_code": invites["HS010"], "browser_key": "race-key-10"},
        ).json()
        client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS011", "invite_code": invites["HS011"], "browser_key": "race-key-11"},
        )
        client.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=headers)
        client.post(f"/api/v1/exams/{exam_id}/start", headers=headers)

        tok10 = j10["attempt_token"]
        att10_id = j10["attempt"]["attempt_id"]
        p10 = client.get("/api/v1/attempts/me/paper", headers={"Authorization": f"Bearer {tok10}"}).json()
        q_first = p10["questions"][0]

        shared_idem = str(uuid.uuid4())

        def _write_once() -> int:
            res = client.post(
                f"/api/v1/attempts/{att10_id}/answers",
                json={
                    "question_version_id": q_first["question_version_id"],
                    "selected_option_ids": [q_first["options"][0]["option_id"]],
                    "idempotency_key": shared_idem,
                },
                headers={"Authorization": f"Bearer {tok10}"},
            )
            return int(res.status_code)

        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(lambda _: _write_once(), range(6)))
        assert all(st == 200 for st in statuses)

        with app.state.session_factory() as db:
            rev_rows = db.execute(
                select(AnswerRevision).where(AnswerRevision.attempt_id == att10_id)
            ).scalars().all()
            assert len(rev_rows) == 1

        # Concurrent submit 5x -> single Submission row
        def _submit_once() -> str:
            r = client.post(
                f"/api/v1/attempts/{att10_id}/submit",
                headers={"Authorization": f"Bearer {tok10}"},
            )
            assert r.status_code == 200
            return str(r.json()["snapshot_hash"])

        with ThreadPoolExecutor(max_workers=5) as pool:
            hashes = list(pool.map(lambda _: _submit_once(), range(5)))
        assert len(set(hashes)) == 1

        # Close exam auto-finalizes HS011 cleanly
        assert client.post(f"/api/v1/exams/{exam_id}/close", json={}, headers=headers).status_code == 200
        with app.state.session_factory() as db:
            subs = db.execute(select(Submission).where(Submission.exam_id == exam_id)).scalars().all()
            assert len(subs) == 2
            modes = {s.submission_mode for s in subs}
            assert modes == {"student_submit", "teacher_close_auto"}


def test_backup_create_verify_dry_run_and_restore_recovery(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    settings = Settings(data_dir=data_dir)
    app = create_app(settings)
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        client.post(
            "/api/v1/classes",
            json={"name": "12A8", "academic_year": "2026-2027"},
            headers=headers,
        )
        _seed_bank_with_n_questions(client, headers, 2)

        bk_res = client.post("/api/v1/system/backups", headers=headers)
        assert bk_res.status_code == 201
        bk_data = bk_res.json()
        bk_id = bk_data["id"]
        assert bk_data["record_counts"]["question_versions"] == 2

        ver_res = client.post(f"/api/v1/system/backups/{bk_id}/verify", headers=headers)
        assert ver_res.status_code == 200
        assert ver_res.json()["checksum_valid"] is True
        assert ver_res.json()["sqlite_integrity_ok"] is True

        # Wipe database file & restore from archive
        archive_path = settings.backups_dir / bk_data["location"]

    settings.db_path.unlink()
    assert not settings.db_path.exists()

    restore_report = restore_backup_archive(settings=settings, archive_path=archive_path)
    assert restore_report.checksum_valid is True
    assert restore_report.sqlite_integrity_ok is True

    restored_app = create_app(settings)
    with TestClient(restored_app) as client2:
        headers2 = _teacher_headers(client2)
        classes = client2.get("/api/v1/classes", headers=headers2).json()
        assert len(classes) == 1
        assert classes[0]["name"] == "12A8"
        bank = client2.get("/api/v1/questions/bank", headers=headers2).json()
        assert len(bank) == 2
        assert json.loads(json.dumps(bank)) is not None
