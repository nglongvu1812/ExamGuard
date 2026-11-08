"""P0 Foundation tests: health, logging redaction, SQLite WAL, Alembic, LAN discovery, launcher."""

from __future__ import annotations

import socket
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.core.logging import redact_text
from app.db.session import backup_sqlite_file, check_db_integrity, create_sqlite_engine
from app.launcher.network import discover_lan_interfaces, generate_qr_svg
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_endpoint_and_no_pii(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "ExamGuardData")
    app = create_app(settings)
    with TestClient(app) as client:
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["db_ok"] is True
        assert body["db_journal_mode"].lower() == "wal"
        assert body["data_dir_writable"] is True
        assert "server_time_utc" in body
        # Ensure log file created cleanly
        assert (settings.logs_dir / "examguard.log").exists()


def test_log_redaction_masks_tokens_and_secrets() -> None:
    raw = 'Authorization: Bearer secret-jwt-token-123 invite_code="AB92X" token=mysecret123'
    redacted = redact_text(raw)
    assert "secret-jwt-token-123" not in redacted
    assert "AB92X" not in redacted
    assert "mysecret123" not in redacted
    assert "[REDACTED]" in redacted


def test_sqlite_wal_and_alembic_upgrade_downgrade(tmp_path: Path) -> None:
    data_dir = tmp_path / "ExamGuardData"
    settings = Settings(data_dir=data_dir)
    settings.ensure_data_dirs()

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    command.upgrade(cfg, "head")
    engine = create_sqlite_engine(settings)
    try:
        db_ok, journal_mode = check_db_integrity(engine)
        assert db_ok is True
        assert journal_mode.lower() == "wal"
    finally:
        engine.dispose()

    backup_file = backup_sqlite_file(settings.db_path, settings.backups_dir, label="test")
    assert backup_file is not None
    assert backup_file.exists()

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_network_discovery_and_qr_offline(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "ExamGuardData", port=8123)
    app = create_app(settings)
    with TestClient(app) as client:
        res = client.get("/api/v1/system/network")
        assert res.status_code == 200
        payload = res.json()
        assert payload["port"] == 8123
        assert payload["offline_ready"] is True
        assert "<svg" in payload["qr_svg"].lower()
        assert len(payload["firewall_guide"]) >= 3

    interfaces = discover_lan_interfaces(8123)
    for iface in interfaces:
        assert not iface.ip.startswith("127.")
        assert ":8123/join" in iface.url

    svg = generate_qr_svg("http://192.168.10.25:8123/join")
    assert "<svg" in svg.lower()


def test_launcher_port_fallback_and_migrations(tmp_path: Path) -> None:
    from desktop.launcher import find_available_port, run_safe_migrations

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    occupied_port = sock.getsockname()[1]
    sock.listen(1)
    try:
        fallback = find_available_port(preferred_port=occupied_port, host="127.0.0.1")
        assert fallback != occupied_port
        assert fallback > 0
    finally:
        sock.close()

    settings = Settings(data_dir=tmp_path / "PortableData")
    run_safe_migrations(settings)
    assert settings.db_path.exists()


def test_offline_spa_serving_and_zero_external_cdn(tmp_path: Path) -> None:
    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not (dist_dir / "index.html").exists():
        return

    index_html = (dist_dir / "index.html").read_text(encoding="utf-8")
    for forbidden in ("fonts.googleapis.com", "unpkg.com", "jsdelivr.net", "cdnjs.cloudflare.com"):
        assert forbidden not in index_html

    settings = Settings(data_dir=tmp_path / "ExamGuardData", static_dir=dist_dir)
    app = create_app(settings)
    with TestClient(app) as client:
        teacher_res = client.get("/")
        assert teacher_res.status_code == 200
        assert "ExamGuard" in teacher_res.text

        student_res = client.get("/join")
        assert student_res.status_code == 200
        assert "ExamGuard" in student_res.text

        missing_api = client.get("/api/v1/nonexistent")
        assert missing_api.status_code == 404

