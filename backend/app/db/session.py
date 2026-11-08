"""SQLite WAL engine, session management, and consistency verification."""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_engine(settings: Settings) -> Engine:
    """Create SQLAlchemy engine configured for SQLite WAL single-host concurrency."""
    engine = create_engine(
        settings.database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": settings.sqlite_busy_timeout_ms / 1000.0,
        },
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms};")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def check_db_integrity(engine: Engine) -> tuple[bool, str]:
    """Run SQLite PRAGMA quick_check and return journal_mode."""
    with engine.connect() as conn:
        integrity = conn.execute(text("PRAGMA quick_check;")).scalar_one()
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar_one()
    return str(integrity).lower() == "ok", str(journal_mode)


def backup_sqlite_file(db_path: Path, backups_dir: Path, label: str = "pre_migrate") -> Path | None:
    """Create a consistent SQLite backup using sqlite3 backup API before migrations."""
    if not db_path.exists():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backups_dir / f"examguard_{label}_{stamp}.db"
    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(target)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    # Keep latest backup copy permissions tidy
    if not target.exists():
        shutil.copy2(db_path, target)
    return target


def get_db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
