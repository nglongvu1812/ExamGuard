"""Windows/Desktop launcher for ExamGuard Portable server lifecycle."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings  # noqa: E402
from app.db.session import backup_sqlite_file  # noqa: E402
from app.main import create_app  # noqa: E402


def find_available_port(preferred_port: int = 8000, host: str = "0.0.0.0") -> int:
    """Return preferred_port if free, otherwise bind port 0 to get an available ephemeral port."""
    for candidate in (preferred_port, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, candidate))
                return int(sock.getsockname()[1])
            except OSError:
                continue
    raise RuntimeError("Không tìm thấy cổng mạng khả dụng cho máy chủ ExamGuard.")


def run_safe_migrations(settings: Settings) -> None:
    """Back up existing SQLite DB and run Alembic migrations cleanly."""
    settings.ensure_data_dirs()
    backup_sqlite_file(settings.db_path, settings.backups_dir, label="pre_migrate")

    alembic_ini = BACKEND_DIR / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


def launch_server(
    data_dir: Path | None = None,
    port: int = 8000,
    open_browser: bool = True,
    host: str = "0.0.0.0",
) -> None:
    resolved_data = data_dir or (ROOT_DIR / "ExamGuardData")
    chosen_port = find_available_port(preferred_port=port, host=host)

    settings = Settings(
        data_dir=resolved_data,
        host=host,
        port=chosen_port,
        static_dir=ROOT_DIR / "frontend" / "dist",
    )
    run_safe_migrations(settings)

    app = create_app(settings)
    config = uvicorn.Config(
        app,
        host=host,
        port=chosen_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    def _shutdown_handler(_signum: int, _frame: object) -> None:
        server.should_exit = True

    signal.signal(signal.SIGINT, _shutdown_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown_handler)

    if open_browser:
        def _open_when_ready() -> None:
            for _ in range(30):
                if server.started:
                    webbrowser.open(f"http://127.0.0.1:{chosen_port}/")
                    return
                time.sleep(0.15)

        threading.Thread(target=_open_when_ready, daemon=True).start()

    print(f"ExamGuard đang chạy tại http://127.0.0.1:{chosen_port}/ (Ctrl+C để dừng an toàn)")
    server.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="ExamGuard Portable Local Server Launcher")
    parser.add_argument("--data-dir", type=Path, default=None, help="Thư mục lưu dữ liệu ExamGuardData")
    parser.add_argument("--port", type=int, default=int(os.getenv("EXAMGUARD_PORT", "8000")))
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt")
    args = parser.parse_args()

    launch_server(
        data_dir=args.data_dir,
        port=args.port,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
