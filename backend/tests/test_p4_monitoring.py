"""P4 Monitoring tests: WebSocket auth, timeouts, non-punitive signals, incidents, zero leaks."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.core.config import Settings
from app.db.models import Attempt, Submission
from app.main import create_app
from app.services.audit_service import verify_audit_chain
from app.services.monitoring_service import evaluate_room_presence
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect


def _teacher_headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/v1/auth/teacher/local-session").json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_bank_with_n_questions(client: TestClient, headers: dict[str, str], n: int = 3) -> list[str]:
    doc = Document()
    keys: list[str] = []
    for i in range(1, n + 1):
        doc.add_paragraph(f"Câu {i}: Số {i} + 1 bằng?")
        doc.add_paragraph(f"A. {i}   B. {i + 1}   C. {i + 2}   D. {i + 3}")
        keys.append(f"{i}B")
    doc.add_paragraph("ĐÁP ÁN: " + " ".join(keys))
    buf = io.BytesIO()
    doc.save(buf)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    imp = client.post(
        "/api/v1/questions/import",
        files={"file": ("de_p4.docx", buf.getvalue(), mime)},
        headers=headers,
    )
    job_id = imp.json()["job_id"]
    client.post(f"/api/v1/questions/import/{job_id}/approve-ready", headers=headers)
    return [item["version_id"] for item in client.get("/api/v1/questions/bank", headers=headers).json()]


def _setup_running_exam_with_two_students(
    client: TestClient,
) -> tuple[dict[str, str], str, list[tuple[str, str]]]:
    headers = _teacher_headers(client)
    cls_id = client.post(
        "/api/v1/classes",
        json={"name": "12A9", "academic_year": "2026-2027"},
        headers=headers,
    ).json()["id"]
    for idx in (1, 2):
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": f"HS40{idx}", "full_name": f"Thí sinh {idx}"},
            headers=headers,
        )

    q_vids = _seed_bank_with_n_questions(client, headers, 3)
    created = client.post(
        "/api/v1/exams",
        json={
            "classroom_id": cls_id,
            "title": "Giám sát P4",
            "duration_s": 900,
            "question_version_ids": q_vids,
            "open_waiting": True,
        },
        headers=headers,
    ).json()
    exam_id = created["exam"]["exam_id"]
    room_code = created["exam"]["room_code"]
    invites = {inv["roster_code"]: inv["invite_code"] for inv in created["invites"]}

    students: list[tuple[str, str]] = []
    for idx in (1, 2):
        code = f"HS40{idx}"
        j = client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": code, "invite_code": invites[code], "browser_key": f"p4-key-{idx}"},
        ).json()
        students.append((j["attempt"]["attempt_id"], j["attempt_token"]))

    assert client.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=headers).status_code == 200
    assert client.post(f"/api/v1/exams/{exam_id}/start", headers=headers).status_code == 200
    return headers, exam_id, students


def test_websocket_auth_rejection_cross_scope_and_zero_key_leak(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers, exam_id, students = _setup_running_exam_with_two_students(client)
        t_tok = headers["Authorization"].removeprefix("Bearer ")
        att1_id, s1_tok = students[0]

        # 1. Missing or tampered token rejected
        with pytest.raises(WebSocketDisconnect), client.websocket_connect(f"/ws/v1/room/{exam_id}"):
            pass
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/ws/v1/room/{exam_id}?token=bad.sig"),
        ):
            pass

        # 2. Student token scoped to exam_id CANNOT connect to another exam_id
        other_exam_id = str(uuid.uuid4())
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/ws/v1/room/{other_exam_id}?token={s1_tok}"),
        ):
            pass

        # 3. Student WS receives welcome & heartbeat_ack with ZERO peer student info or answer keys
        with client.websocket_connect(f"/ws/v1/room/{exam_id}?token={s1_tok}") as ws_s1:
            welcome = ws_s1.receive_json()
            assert welcome["type"] == "welcome"
            assert welcome["attempt_id"] == att1_id
            raw_welcome = str(welcome).lower()
            assert "hs402" not in raw_welcome
            assert "correct_option_ids" not in raw_welcome

            ws_s1.send_json({"type": "heartbeat"})
            hb = ws_s1.receive_json()
            assert hb["type"] == "heartbeat_ack"
            assert hb["presence_state"] == "ACTIVE"

            ws_s1.send_json(
                {
                    "type": "client_event",
                    "event_type": "APP_HIDDEN",
                    "details": {"visibility_state": "hidden"},
                }
            )
            ev_ack = ws_s1.receive_json()
            assert ev_ack["type"] == "event_ack"
            assert ev_ack["event_type"] == "APP_HIDDEN"

        # 4. Teacher WS receives live snapshot including student 1's hidden_event_count == 1
        with client.websocket_connect(f"/ws/v1/room/{exam_id}?token={t_tok}") as ws_t:
            t_welcome = ws_t.receive_json()
            assert t_welcome["type"] == "welcome"
            roster = {r["attempt_id"]: r for r in t_welcome["snapshot"]["roster"]}
            assert roster[att1_id]["hidden_event_count"] == 1
            # Non-punitive guarantee: APP_HIDDEN alone does NOT lock student or call it cheating
            assert roster[att1_id]["attempt_state"] == "ACTIVE"

        # 5. Teacher resets student 1 device -> stale student token rejected on WS & token refresh
        client.post(
            f"/api/v1/rooms/{exam_id}/attempts/{att1_id}/reset-device",
            json={"reason": "Mất kết nối máy cũ"},
            headers=headers,
        )
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/ws/v1/room/{exam_id}?token={s1_tok}"),
        ):
            pass


def test_grace_thresholds_auto_lock_and_teacher_resolution_flows(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers, exam_id, students = _setup_running_exam_with_two_students(client)
        att1_id, s1_tok = students[0]
        att2_id, s2_tok = students[1]

        # Student 1 saves an answer before disconnect
        p1 = client.get("/api/v1/attempts/me/paper", headers={"Authorization": f"Bearer {s1_tok}"}).json()
        q0 = p1["questions"][0]
        save_res = client.post(
            f"/api/v1/attempts/{att1_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": [q0["options"][0]["option_id"]],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {s1_tok}"},
        )
        assert save_res.status_code == 200

        # Teacher updates custom thresholds: suspected=4s, disconnect=10s, lock_after=20s
        pol_res = client.patch(
            f"/api/v1/monitoring/exams/{exam_id}/policy",
            json={
                "heartbeat_s": 2,
                "suspected_s": 4,
                "disconnect_s": 10,
                "lock_after_s": 20,
                "grace_submit_s": 30,
            },
            headers=headers,
        )
        assert pol_res.status_code == 200
        assert pol_res.json()["lock_after_s"] == 20

        # Simulate elapsed silence on Student 1: 6s -> SUSPECTED, 12s -> DISCONNECTED, heartbeat -> RECONNECTED
        base_now = datetime.now(UTC)
        with app.state.session_factory() as db:
            a1 = db.get(Attempt, att1_id)
            assert a1 is not None
            a1.last_heartbeat_at = base_now - timedelta(seconds=6)
            db.commit()
            assert evaluate_room_presence(db, exam_id=exam_id, now=base_now) is True
            db.expire_all()
            assert db.get(Attempt, att1_id).presence_state == "SUSPECTED"  # type: ignore[union-attr]

            a1 = db.get(Attempt, att1_id)
            assert a1 is not None
            a1.last_heartbeat_at = base_now - timedelta(seconds=12)
            db.commit()
            assert evaluate_room_presence(db, exam_id=exam_id, now=base_now) is True
            db.expire_all()
            assert db.get(Attempt, att1_id).presence_state == "DISCONNECTED"  # type: ignore[union-attr]

        # Reconnect heartbeat recovers DISCONNECTED -> ACTIVE and increments reconnect_count
        hb_recover = client.post(
            f"/api/v1/attempts/{att1_id}/heartbeat",
            headers={"Authorization": f"Bearer {s1_tok}"},
        )
        assert hb_recover.status_code == 200
        assert hb_recover.json()["presence_state"] == "ACTIVE"

        # Now exceed lock_after_s (22s > 20s) -> LOCKED_PENDING_REVIEW + OPEN Incident
        with app.state.session_factory() as db:
            a1 = db.get(Attempt, att1_id)
            assert a1 is not None
            a1.last_heartbeat_at = base_now - timedelta(seconds=22)
            db.commit()
            evaluate_room_presence(db, exam_id=exam_id, now=base_now)

        # Answer writes MUST be rejected while locked
        locked_write = client.post(
            f"/api/v1/attempts/{att1_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": [q0["options"][1]["option_id"]],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {s1_tok}"},
        )
        assert locked_write.status_code == 403

        # Sync still shows locked status safely without wiping answers
        sync_locked = client.get(
            f"/api/v1/attempts/{att1_id}/sync",
            headers={"Authorization": f"Bearer {s1_tok}"},
        ).json()
        assert sync_locked["attempt_state"] == "LOCKED_PENDING_REVIEW"
        assert "Cần giáo viên xác minh" in (sync_locked["incident_reason"] or "")

        # Teacher resolves incident by extending +5 minutes -> unlocks & adds 300s extra time
        resolve_res = client.post(
            f"/api/v1/monitoring/exams/{exam_id}/attempts/{att1_id}/resolve",
            json={
                "action": "extend_time",
                "reason": "Wi-Fi bàn cuối chập chờn đã kết nối lại",
                "extend_minutes": 5,
            },
            headers=headers,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["attempt_state"] == "ACTIVE"
        assert resolve_res.json()["extra_time_s"] == 300

        # Refresh token endpoint works cleanly for Student 1
        ref_res = client.post(
            f"/api/v1/attempts/{att1_id}/refresh-token",
            headers={"Authorization": f"Bearer {s1_tok}"},
        )
        assert ref_res.status_code == 200
        fresh_tok1 = ref_res.json()["attempt_token"]

        # Student 1 can save again with fresh token
        ok_after_unlock = client.post(
            f"/api/v1/attempts/{att1_id}/answers",
            json={
                "question_version_id": q0["question_version_id"],
                "selected_option_ids": [q0["options"][1]["option_id"]],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {fresh_tok1}"},
        )
        assert ok_after_unlock.status_code == 200

        # Student 2 saves answer then gets manually locked & terminated -> preserves ACKed answer snapshot!
        p2 = client.get("/api/v1/attempts/me/paper", headers={"Authorization": f"Bearer {s2_tok}"}).json()
        client.post(
            f"/api/v1/attempts/{att2_id}/answers",
            json={
                "question_version_id": p2["questions"][0]["question_version_id"],
                "selected_option_ids": [p2["questions"][0]["options"][0]["option_id"]],
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {s2_tok}"},
        )
        assert (
            client.post(
                f"/api/v1/monitoring/exams/{exam_id}/attempts/{att2_id}/lock",
                json={"reason": "Dùng tài liệu giấy sau khi đã nhắc nhở"},
                headers=headers,
            ).status_code
            == 200
        )
        term_res = client.post(
            f"/api/v1/monitoring/exams/{exam_id}/attempts/{att2_id}/resolve",
            json={"action": "terminate", "reason": "Xác nhận lập biên bản dừng bài thi"},
            headers=headers,
        )
        assert term_res.status_code == 200
        assert term_res.json()["attempt_state"] == "ENDED_WITH_REVIEW"

        # Student cannot call teacher endpoints & Student 1 cannot view Student 2's timeline
        mon_forbidden = client.get(
            f"/api/v1/monitoring/exams/{exam_id}",
            headers={"Authorization": f"Bearer {s1_tok}"},
        )
        assert mon_forbidden.status_code == 403
        assert (
            client.get(
                f"/api/v1/monitoring/exams/{exam_id}/attempts/{att2_id}/timeline",
                headers={"Authorization": f"Bearer {s1_tok}"},
            ).status_code
            == 403
        )
        # Teacher timeline includes full events & resolved incidents
        tl = client.get(
            f"/api/v1/monitoring/exams/{exam_id}/attempts/{att1_id}/timeline",
            headers=headers,
        ).json()
        assert tl["reconnect_count"] >= 1
        assert len(tl["incidents"]) >= 1
        assert tl["incidents"][0]["state"] == "RESOLVED_EXTENDED"

        with app.state.session_factory() as db:
            sub2 = db.execute(select(Submission).where(Submission.attempt_id == att2_id)).scalar_one()
            assert sub2.submission_mode == "teacher_terminate_review"
            ok_chain, ev_count = verify_audit_chain(db)
            assert ok_chain is True
            assert ev_count >= 5
