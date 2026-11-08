"""P1 tests: Classroom/Student CRUD, CSV/XLSX dry-run import, invites, binding, races, isolation."""

from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.db.models import Attempt, StudentInvite
from app.main import create_app
from app.services.audit_service import verify_audit_chain
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select


def _teacher_headers(client: TestClient) -> dict[str, str]:
    res = client.post("/api/v1/auth/teacher/local-session")
    assert res.status_code == 200
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_classroom_student_crud_preserves_uuid_on_rename(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)

        cls_res = client.post(
            "/api/v1/classes",
            json={"name": "12A1", "academic_year": "2026-2027"},
            headers=headers,
        )
        assert cls_res.status_code == 201
        cls_id = cls_res.json()["id"]

        st_res = client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS001", "full_name": "Nguyễn Văn An"},
            headers=headers,
        )
        assert st_res.status_code == 201
        student_id = st_res.json()["id"]

        # Duplicate roster code must fail with 409
        dup_res = client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "hs001", "full_name": "Người trùng mã"},
            headers=headers,
        )
        assert dup_res.status_code == 409

        # Rename keeps identical UUID
        patch_res = client.patch(
            f"/api/v1/students/{student_id}",
            json={"full_name": "Nguyễn Văn An (Đã sửa)"},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["id"] == student_id
        assert patch_res.json()["full_name"] == "Nguyễn Văn An (Đã sửa)"


def test_import_40_students_xlsx_dry_run_duplicates_and_malformed(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        cls_id = client.post(
            "/api/v1/classes",
            json={"name": "12A2", "academic_year": "2026-2027"},
            headers=headers,
        ).json()["id"]

        # Generate synthetic 40-student XLSX in memory
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["Mã học sinh", "Họ và tên", "Ghi chú"])
        for idx in range(1, 41):
            ws.append([f"HS{idx:03d}", f"Học sinh Mẫu {idx}", "Mẫu"])
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

        xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        preview = client.post(
            f"/api/v1/classes/{cls_id}/import/preview",
            files={"file": ("roster.xlsx", xlsx_bytes, xlsx_mime)},
            headers=headers,
        )
        assert preview.status_code == 200
        p_data = preview.json()
        assert p_data["new_count"] == 40
        assert p_data["has_conflicts"] is False

        commit = client.post(
            f"/api/v1/classes/{cls_id}/import/commit",
            json={"rows": p_data["rows"], "duplicate_policy": "skip"},
            headers=headers,
        )
        assert commit.status_code == 200
        assert commit.json()["added"] == 40

        # Dry-run CSV updating 2 names + 1 intra-file duplicate must report conflicts
        csv_text = "roster_code,full_name\nHS001,Tên Mới 1\nHS002,Tên Mới 2\nHS002,Trùng Trong File\n"
        preview_dup = client.post(
            f"/api/v1/classes/{cls_id}/import/preview",
            files={"file": ("update.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=headers,
        )
        assert preview_dup.status_code == 200
        dup_json = preview_dup.json()
        assert dup_json["has_conflicts"] is True
        assert dup_json["conflict_count"] == 3

        # Commit update_name preserves total count = 40
        commit_upd = client.post(
            f"/api/v1/classes/{cls_id}/import/commit",
            json={"rows": dup_json["rows"], "duplicate_policy": "update_name"},
            headers=headers,
        )
        assert commit_upd.status_code == 200
        assert commit_upd.json()["updated"] == 2
        students_list = client.get(f"/api/v1/classes/{cls_id}/students", headers=headers).json()
        assert len(students_list) == 40

        # Malformed file rejected safely
        bad_file = client.post(
            f"/api/v1/classes/{cls_id}/import/preview",
            files={"file": ("bad.xlsx", b"not-a-zip-xlsx", "application/octet-stream")},
            headers=headers,
        )
        assert bad_file.status_code == 400


def test_room_join_two_devices_reset_audit_and_cross_student_isolation(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        cls_id = client.post(
            "/api/v1/classes",
            json={"name": "12A3", "academic_year": "2026-2027"},
            headers=headers,
        ).json()["id"]

        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS101", "full_name": "Trần Bình"},
            headers=headers,
        )
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS102", "full_name": "Lê Chi"},
            headers=headers,
        )

        room_res = client.post(
            "/api/v1/rooms",
            json={"classroom_id": cls_id, "title": "Kiểm tra 15p", "duration_s": 900},
            headers=headers,
        )
        assert room_res.status_code == 201
        room_data = room_res.json()
        exam_id = room_data["room"]["exam_id"]
        room_code = room_data["room"]["room_code"]
        invites_by_code = {inv["roster_code"]: inv["invite_code"] for inv in room_data["invites"]}

        # Verify plaintext invite codes are NOT stored in DB
        with app.state.session_factory() as db:
            stored_hashes = [inv.code_hash for inv in db.execute(select(StudentInvite)).scalars().all()]
            for plain in invites_by_code.values():
                assert plain not in stored_hashes

        # Student A joins on browser 1
        join_a1 = client.post(
            f"/api/v1/room/{room_code}/join",
            json={
                "roster_code": "HS101",
                "invite_code": invites_by_code["HS101"],
                "browser_key": "browser-device-1-key",
            },
        )
        assert join_a1.status_code == 200
        token_a1 = join_a1.json()["attempt_token"]
        attempt_a_id = join_a1.json()["attempt"]["attempt_id"]
        assert join_a1.json()["attempt"]["state"] == "PENDING_APPROVAL"

        # Same student on SECOND browser must be rejected with 409 (no duplicate attempt created)
        join_a2 = client.post(
            f"/api/v1/room/{room_code}/join",
            json={
                "roster_code": "HS101",
                "invite_code": invites_by_code["HS101"],
                "browser_key": "browser-device-2-key",
            },
        )
        assert join_a2.status_code == 409

        # Student B joins
        join_b = client.post(
            f"/api/v1/room/{room_code}/join",
            json={
                "roster_code": "HS102",
                "invite_code": invites_by_code["HS102"],
                "browser_key": "browser-b-device-key",
            },
        )
        assert join_b.status_code == 200
        token_b = join_b.json()["attempt_token"]

        # Negative security tests: Student B cannot read Student A's attempt or call teacher endpoints
        cross_read = client.get(
            f"/api/v1/attempts/{attempt_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert cross_read.status_code == 403

        student_calling_teacher = client.get(
            "/api/v1/classes",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert student_calling_teacher.status_code == 403

        unauth_teacher = client.get("/api/v1/classes")
        assert unauth_teacher.status_code == 401

        # Teacher approves A
        approve_res = client.post(
            f"/api/v1/rooms/{exam_id}/attempts/{attempt_a_id}/approve",
            headers=headers,
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["state"] == "READY"

        # Teacher resets A's device with mandatory reason -> rebind works, old token invalidated
        reset_res = client.post(
            f"/api/v1/rooms/{exam_id}/attempts/{attempt_a_id}/reset-device",
            json={"reason": "Học sinh bị hết pin điện thoại, đổi sang máy dự phòng"},
            headers=headers,
        )
        assert reset_res.status_code == 200

        rebind_a2 = client.post(
            f"/api/v1/room/{room_code}/join",
            json={
                "roster_code": "HS101",
                "invite_code": invites_by_code["HS101"],
                "browser_key": "browser-device-2-key",
            },
        )
        assert rebind_a2.status_code == 200
        assert rebind_a2.json()["attempt"]["attempt_id"] == attempt_a_id

        old_token_check = client.get(
            "/api/v1/attempts/me",
            headers={"Authorization": f"Bearer {token_a1}"},
        )
        assert old_token_check.status_code == 401

        # Verify audit hash chain integrity
        with app.state.session_factory() as db:
            ok, count = verify_audit_chain(db)
            assert ok is True
            assert count >= 3
            attempts_for_a = db.execute(select(Attempt).where(Attempt.exam_id == exam_id)).scalars().all()
            assert len(attempts_for_a) == 2  # A + B only, never duplicated


def test_join_rate_limit_and_expired_invite(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path / "Data"))
    with TestClient(app) as client:
        headers = _teacher_headers(client)
        cls_id = client.post(
            "/api/v1/classes",
            json={"name": "12A4", "academic_year": "2026-2027"},
            headers=headers,
        ).json()["id"]
        client.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS201", "full_name": "Phạm Dũng"},
            headers=headers,
        )
        room = client.post(
            "/api/v1/rooms",
            json={"classroom_id": cls_id, "title": "Test Rate", "duration_s": 600},
            headers=headers,
        ).json()
        room_code = room["room"]["room_code"]
        valid_code = room["invites"][0]["invite_code"]

        # Trigger rate limit after 10 bad attempts
        for _ in range(10):
            r = client.post(
                f"/api/v1/room/{room_code}/join",
                json={"roster_code": "HS201", "invite_code": "WRONG1", "browser_key": "dev-key-12345"},
            )
            assert r.status_code == 401

        blocked = client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS201", "invite_code": valid_code, "browser_key": "dev-key-12345"},
        )
        assert blocked.status_code == 429

        # Test invite expiry in DB
        app.state.join_rate_limiter.reset(f"testclient:{room_code}")
        with app.state.session_factory() as db:
            inv = db.execute(select(StudentInvite)).scalar_one()
            inv.expires_at = datetime.now(UTC) - timedelta(minutes=5)
            db.commit()

        expired = client.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS201", "invite_code": valid_code, "browser_key": "dev-key-12345"},
        )
        assert expired.status_code == 401


def test_concurrent_join_race_produces_single_attempt(tmp_path: Path) -> None:
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
            json={"roster_code": "HS301", "full_name": "Hoàng Race"},
            headers=headers,
        )
        room = client.post(
            "/api/v1/rooms",
            json={"classroom_id": cls_id, "title": "Race Test", "duration_s": 600},
            headers=headers,
        ).json()
        room_code = room["room"]["room_code"]
        code = room["invites"][0]["invite_code"]

        def _join(idx: int) -> int:
            res = client.post(
                f"/api/v1/room/{room_code}/join",
                json={"roster_code": "HS301", "invite_code": code, "browser_key": f"race-device-{idx}-abcdef"},
            )
            return res.status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(_join, range(4)))

        assert 200 in statuses
        with app.state.session_factory() as db:
            rows = db.execute(select(Attempt)).scalars().all()
            assert len(rows) == 1
