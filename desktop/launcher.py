"""Windows/Desktop Portable launcher for ExamGuard Local Server lifecycle."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sqlite3
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from alembic import command
from alembic.config import Config
from alembic.util import CommandError
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from app.core.config import Settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP_RELEASE_VERSION = "0.1.1"


@dataclass(frozen=True)
class BundlePaths:
    resource_root: Path
    backend_dir: Path
    static_dir: Path
    default_data_dir: Path


def resolve_bundle_paths() -> BundlePaths:
    """Resolve bundled assets and portable writable ExamGuardData for source vs frozen EXE."""
    is_frozen = bool(getattr(sys, "frozen", False))
    meipass = getattr(sys, "_MEIPASS", None)
    if is_frozen and isinstance(meipass, str):
        bundle_root = Path(meipass).resolve()
        exe_parent = Path(sys.executable).resolve().parent
        return BundlePaths(
            resource_root=bundle_root,
            backend_dir=bundle_root,
            static_dir=bundle_root / "frontend" / "dist",
            default_data_dir=exe_parent / "ExamGuardData",
        )

    repo_root = Path(__file__).resolve().parents[1]
    return BundlePaths(
        resource_root=repo_root,
        backend_dir=repo_root / "backend",
        static_dir=repo_root / "frontend" / "dist",
        default_data_dir=repo_root / "ExamGuardData",
    )


def _ensure_backend_on_path(paths: BundlePaths | None = None) -> BundlePaths:
    resolved = paths or resolve_bundle_paths()
    backend_str = str(resolved.backend_dir)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)
    return resolved


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
    paths = _ensure_backend_on_path()
    from app.db.session import backup_sqlite_file

    settings.ensure_data_dirs()
    backup_sqlite_file(settings.db_path, settings.backups_dir, label="pre_migrate")

    alembic_ini = paths.backend_dir / "alembic.ini"
    alembic_dir = paths.backend_dir / "alembic"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


def launch_server(
    data_dir: Path | None = None,
    port: int = 8000,
    open_browser: bool = True,
    host: str = "0.0.0.0",
) -> None:
    paths = _ensure_backend_on_path()
    from app.core.config import Settings
    from app.main import create_app

    resolved_data = (data_dir or paths.default_data_dir).resolve()
    chosen_port = find_available_port(preferred_port=port, host=host)

    settings = Settings(
        data_dir=resolved_data,
        host=host,
        port=chosen_port,
        static_dir=paths.static_dir,
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
            for _ in range(40):
                if server.started:
                    webbrowser.open(f"http://127.0.0.1:{chosen_port}/")
                    return
                time.sleep(0.15)

        threading.Thread(target=_open_when_ready, daemon=True).start()

    print(
        f"ExamGuard {APP_RELEASE_VERSION} đang chạy tại http://127.0.0.1:{chosen_port}/ "
        f"(Dữ liệu: {resolved_data}) — Ctrl+C để dừng an toàn."
    )
    server.run()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ExamGuard Portable Local Server Launcher")
    parser.add_argument("--data-dir", type=Path, default=None, help="Thư mục lưu dữ liệu ExamGuardData")
    parser.add_argument("--host", type=str, default=os.getenv("EXAMGUARD_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EXAMGUARD_PORT", "8000")))
    parser.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt")
    parser.add_argument("--version", action="store_true", help="Hiển thị phiên bản và thoát")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"ExamGuard {APP_RELEASE_VERSION}")
        return 0

    try:
        launch_server(
            data_dir=args.data_dir,
            port=args.port,
            open_browser=not args.no_browser,
            host=args.host,
        )
    except PermissionError as exc:
        print(f"[LỖI QUYỀN GHI] {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError, sqlite3.Error, SQLAlchemyError, CommandError) as exc:
        print(f"[LỖI KHỞI ĐỘNG] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
