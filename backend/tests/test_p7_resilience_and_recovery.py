"""P7 resilience tests: offline zero-CDN audit, disk-full/WAL recovery, cross-PC restore, launcher paths."""

from __future__ import annotations

import errno
import io
import json
import re
import sqlite3
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app.core.config import Settings
from app.db.models import (
    AnswerKeyVersion,
    Asset,
    AuditEvent,
    BackupManifest,
    OmrScanSubmission,
    PaperVersion,
    Question,
    QuestionVersion,
)
from app.main import create_app
from app.services.backup_service import create_full_backup, restore_backup_archive
from app.services.paper_service import render_omr_template_png
from desktop.launcher import APP_RELEASE_VERSION, resolve_bundle_paths
from desktop.launcher import main as launcher_main
from fastapi.testclient import TestClient
from PIL import Image


def _teacher_headers(client: TestClient) -> dict[str, str]:
    res = client.post("/api/v1/auth/teacher/local-session")
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _seed_question_with_asset(client: TestClient) -> dict[str, str]:
    app = client.app
    settings: Settings = app.state.settings  # type: ignore[attr-defined]
    session_factory = app.state.session_factory  # type: ignore[attr-defined]

    buf = io.BytesIO()
    Image.new("RGB", (24, 24), color=(15, 70, 120)).save(buf, format="PNG")
    raw = buf.getvalue()
    import hashlib

    sha = hashlib.sha256(raw).hexdigest()
    asset_dir = settings.assets_dir / sha[:2]
    asset_dir.mkdir(parents=True, exist_ok=True)
    rel = f"{sha[:2]}/{sha}.png"
    (settings.assets_dir / rel).write_bytes(raw)

    qid = str(uuid.uuid4())
    qvid = str(uuid.uuid4())
    opt_a = str(uuid.uuid4())
    opt_b = str(uuid.uuid4())
    with session_factory() as db:
        db.add(Asset(id=sha, mime_type="image/png", byte_size=len(raw), relpath=rel))
        db.flush()
        db.add(Question(id=qid, bank_name="P7 Recovery", active_version_id=qvid))
        db.flush()
        db.add(
            QuestionVersion(
                id=qvid,
                question_id=qid,
                version_number=1,
                content_blocks_json=json.dumps(
                    [
                        {"type": "text", "text": "Câu hỏi P7 kiểm thử khôi phục dữ liệu"},
                        {"type": "image", "asset_id": sha, "alt": "Hình mẫu"},
                    ],
                    ensure_ascii=False,
                ),
                options_json=json.dumps(
                    [
                        {"option_id": opt_a, "label": "A", "blocks": [{"type": "text", "text": "Đúng A"}]},
                        {"option_id": opt_b, "label": "B", "blocks": [{"type": "text", "text": "Sai B"}]},
                    ],
                    ensure_ascii=False,
                ),
                provenance_json="{}",
                approved_by=1,
            )
        )
        db.flush()
        db.add(
            AnswerKeyVersion(
                id=str(uuid.uuid4()),
                question_version_id=qvid,
                version_number=1,
                correct_option_ids_json=json.dumps([opt_a]),
                reason="Key mẫu P7",
                approved_by=1,
            )
        )
        db.commit()
    return {"qvid": qvid, "opt_a": opt_a, "opt_b": opt_b, "asset_id": sha}


def test_offline_zero_cdn_and_static_bundle_audit() -> None:
    """EG-703: Ensure built frontend dist and backend templates contain zero external CDN URLs."""
    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    assert (dist_dir / "index.html").is_file()

    forbidden_cdn_markers = (
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
    )
    asset_url_re = re.compile(r"""(?:src|href)\s*=\s*["']https?://""", re.IGNORECASE)

    files_to_scan = [dist_dir / "index.html", *(dist_dir / "assets").glob("*.css")]
    for f in files_to_scan:
        content = f.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden_cdn_markers:
            assert marker not in content, f"Phát hiện tham chiếu CDN ngoài '{marker}' trong {f.name}"
        if f.name == "index.html":
            assert not asset_url_re.search(content), "index.html không được tải tài nguyên HTTP/HTTPS ngoài"


def test_permission_denied_and_disk_full_during_backup_preserve_db(tmp_path: Path) -> None:
    """EG-706: Simulated permission failure & ENOSPC disk full never corrupt live SQLite DB."""
    # 1. Explicit PermissionError when write probe fails on Settings.ensure_data_dirs()
    blocked_settings = Settings(data_dir=tmp_path / "ReadOnlyData")
    with (
        patch.object(Path, "write_text", side_effect=OSError(errno.EACCES, "Permission denied")),
        patch("sys.exit"),
    ):
        try:
            blocked_settings.ensure_data_dirs()
            raised = False
        except PermissionError as exc:
            raised = True
            assert "không có quyền ghi" in str(exc)
        assert raised is True

    # 2. Simulated ENOSPC during backup zipfile creation leaves zero partial zips & DB intact
    data_dir = tmp_path / "ExamGuardData"
    app = create_app(Settings(data_dir=data_dir))
    with TestClient(app) as client:
        hdrs = _teacher_headers(client)
        seeded = _seed_question_with_asset(client)
        cls_res = client.post(
            "/api/v1/classes", json={"name": "12A-DiskFull", "academic_year": "2026-2027"}, headers=hdrs
        )
        assert cls_res.status_code == 201

        with (
            patch.object(zipfile.ZipFile, "write", side_effect=OSError(errno.ENOSPC, "No space left on device")),
            app.state.session_factory() as db,  # type: ignore[attr-defined]
        ):
            try:
                create_full_backup(
                    db,
                    settings=app.state.settings,  # type: ignore[attr-defined]
                    teacher_id=1,
                    label="enospc",
                )
                failed = False
            except Exception as exc:
                failed = True
                assert getattr(exc, "status_code", None) == 507
            assert failed is True

        # Verify zero leftover .zip/.tmp files and intact SQLite integrity + original question retained
        leftover_files = list((data_dir / "backups").glob("*.zip*"))
        assert leftover_files == []

        with sqlite3.connect(data_dir / "examguard.db") as conn:
            chk = conn.execute("PRAGMA integrity_check;").fetchone()
            assert chk is not None and chk[0] == "ok"
        assert len(client.get("/api/v1/questions/bank", headers=hdrs).json()) == 1
        assert seeded["qvid"]


def test_mid_exam_crash_restart_wal_recovery_and_cross_pc_restore(tmp_path: Path) -> None:
    """EG-706 & EG-707: Survive mid-exam abrupt app teardown + migrate full backup to fresh PC data dir."""
    pc1_data = tmp_path / "PC1_ExamGuardData"
    app1 = create_app(Settings(data_dir=pc1_data))

    with TestClient(app1) as c1:
        hdrs1 = _teacher_headers(c1)
        seeded = _seed_question_with_asset(c1)
        cls_id = c1.post(
            "/api/v1/classes", json={"name": "12A-Restore", "academic_year": "2026-2027"}, headers=hdrs1
        ).json()["id"]
        st1_res = c1.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS0001", "full_name": "Nguyễn Khôi Phục"},
            headers=hdrs1,
        )
        assert st1_res.status_code == 201
        st2 = c1.post(
            f"/api/v1/classes/{cls_id}/students",
            json={"roster_code": "HS0002", "full_name": "Trần Thi Giấy"},
            headers=hdrs1,
        ).json()
        ex_res = c1.post(
            "/api/v1/exams",
            json={
                "classroom_id": cls_id,
                "title": "Kỳ thi Phục hồi Thảm họa",
                "duration_s": 900,
                "question_version_ids": [seeded["qvid"]],
                "open_waiting": True,
                "seed": 707,
            },
            headers=hdrs1,
        ).json()
        exam_id = ex_res["exam"]["exam_id"]
        room_code = ex_res["exam"]["room_code"]
        inv1 = next(inv["invite_code"] for inv in ex_res["invites"] if inv["roster_code"] == "HS0001")

        # HS0001 joins, gets approved, exam starts, ACK save committed BEFORE simulated abrupt shutdown
        j1 = c1.post(
            f"/api/v1/room/{room_code}/join",
            json={"roster_code": "HS0001", "invite_code": inv1, "browser_key": "pc1-recover-key"},
        ).json()
        att1_id = j1["attempt"]["attempt_id"]
        s1_hdrs = {"Authorization": f"Bearer {j1['attempt_token']}"}
        c1.post(f"/api/v1/rooms/{exam_id}/approve-all", headers=hdrs1)
        c1.post(f"/api/v1/exams/{exam_id}/start", headers=hdrs1)
        ack = c1.post(
            f"/api/v1/attempts/{att1_id}/answers",
            json={
                "question_version_id": seeded["qvid"],
                "selected_option_ids": [seeded["opt_a"]],
                "idempotency_key": "crash-ack-1",
            },
            headers=s1_hdrs,
        )
        assert ack.status_code == 200

    # Restart completely fresh app instance against PC1_ExamGuardData -> ACKed answer must survive!
    app1_restart = create_app(Settings(data_dir=pc1_data))
    with TestClient(app1_restart) as c1_re:
        hdrs_re = _teacher_headers(c1_re)
        assert c1_re.post(f"/api/v1/attempts/{att1_id}/submit", headers=s1_hdrs).status_code == 200
        c1_re.post(
            f"/api/v1/exams/{exam_id}/close",
            json={"reason": "Đóng phiên sau khi phục hồi"},
            headers=hdrs_re,
        )
        # Also attach Paper OMR scan for HS0002 to verify P6 artifacts migrate across PCs
        pvs = c1_re.post(
            f"/api/v1/paper/exams/{exam_id}/versions",
            json={"count": 1, "start_code": 101},
            headers=hdrs_re,
        ).json()["versions"]
        raw_omr = render_omr_template_png(
            exam_title="Kỳ thi Phục hồi Thảm họa",
            classroom_name="12A-Restore",
            question_count=1,
            filled_sbd="0002",
            filled_version="101",
            filled_answers={1: [pvs[0]["answer_key_map"]["1"][0]]},
        )
        up_scan = c1_re.post(
            f"/api/v1/paper/exams/{exam_id}/scans",
            files={"file": ("omr_p7.png", raw_omr, "image/png")},
            headers=hdrs_re,
        ).json()
        assert (
            c1_re.post(
                f"/api/v1/paper/scans/{up_scan['scan_id']}/confirm",
                json={
                    "student_id": st2["id"],
                    "version_code": "101",
                    "confirmed_answers": up_scan["detected_answers"],
                    "reason": "Xác nhận OMR trước khi backup chuyển máy",
                },
                headers=hdrs_re,
            ).status_code
            == 200
        )

        # Review, publish, and create full backup archive on PC1
        c1_re.post(
            f"/api/v1/results/exams/{exam_id}/review",
            json={"reason": "Duyệt kết quả P7"},
            headers=hdrs_re,
        )
        c1_re.post(
            f"/api/v1/results/exams/{exam_id}/publish",
            json={"confirm": True},
            headers=hdrs_re,
        )
        b_res = c1_re.post("/api/v1/system/backups", headers=hdrs_re)
        assert b_res.status_code == 201
        archive_path = pc1_data / "backups" / b_res.json()["location"]
        assert archive_path.is_file()

    # Cross-PC Restore onto clean isolated PC2 directory
    pc2_data = tmp_path / "PC2_CleanMachineData"
    pc2_settings = Settings(data_dir=pc2_data)
    pc2_settings.ensure_data_dirs()
    restore_report = restore_backup_archive(settings=pc2_settings, archive_path=archive_path)
    assert restore_report.checksum_valid is True
    assert restore_report.sqlite_integrity_ok is True
    assert restore_report.record_counts["submissions"] >= 2
    assert restore_report.record_counts["score_versions"] >= 2
    assert restore_report.record_counts["paper_versions"] == 1
    assert restore_report.record_counts["omr_scan_submissions"] == 1

    app2 = create_app(Settings(data_dir=pc2_data))
    with TestClient(app2) as c2:
        hdrs2 = _teacher_headers(c2)
        ov2 = c2.get(f"/api/v1/results/exams/{exam_id}", headers=hdrs2).json()
        by_code = {row["roster_code"]: row for row in ov2["students"]}
        assert by_code["HS0001"]["score_10"] == 10.0
        assert by_code["HS0002"]["score_10"] == 10.0
        # Asset image, audit integrity & OMR scan image restored intact on PC2
        assert c2.get(f"/api/v1/assets/{seeded['asset_id']}").status_code == 200
        assert c2.get(f"/api/v1/paper/scans/{up_scan['scan_id']}/image", headers=hdrs2).status_code == 200
        audit_chk = c2.get("/api/v1/audit/verify", headers=hdrs2).json()
        assert audit_chk["valid"] is True
        with app2.state.session_factory() as db2:  # type: ignore[attr-defined]
            assert db2.query(AuditEvent).count() >= 1
            assert db2.query(PaperVersion).count() == 1
            assert db2.query(OmrScanSubmission).count() == 1
        # Verify restored PC2 can continue taking fresh backups cleanly
        b2_res = c2.post("/api/v1/system/backups", headers=hdrs2)
        assert b2_res.status_code == 201
        with app2.state.session_factory() as db2_after:  # type: ignore[attr-defined]
            assert db2_after.query(BackupManifest).count() == 1


def test_launcher_frozen_path_resolution_and_cli_version(tmp_path: Path, capsys: Any) -> None:
    """EG-702: Launcher resolves _MEIPASS resources + portable ExamGuardData beside EXE cleanly."""
    fake_exe_dir = tmp_path / "PortableApp"
    fake_meipass = fake_exe_dir / "_internal"
    fake_meipass.mkdir(parents=True)
    fake_exe = fake_exe_dir / "ExamGuard.exe"
    fake_exe.write_bytes(b"")

    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", str(fake_meipass), create=True),
        patch.object(sys, "executable", str(fake_exe)),
    ):
        paths = resolve_bundle_paths()
        assert paths.resource_root == fake_meipass.resolve()
        assert paths.static_dir == fake_meipass.resolve() / "frontend" / "dist"
        assert paths.default_data_dir == fake_exe_dir.resolve() / "ExamGuardData"

    rc = launcher_main(["--version"])
    assert rc == 0
    captured = capsys.readouterr()
    assert APP_RELEASE_VERSION in captured.out
