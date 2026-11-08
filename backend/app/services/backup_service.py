"""Consistent SQLite + asset archive backup creation and checksum-verified dry-run restore."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.db.models import BackupManifest
from app.services.audit_service import record_audit_event
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class VerifyRestoreReport:
    manifest_id: str | None
    archive_name: str
    schema_version: str
    checksum_valid: bool
    sqlite_integrity_ok: bool
    record_counts: dict[str, int]
    dry_run: bool


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_record_counts(db: Session) -> dict[str, int]:
    tables = [
        "classrooms",
        "students",
        "questions",
        "question_versions",
        "exams",
        "attempts",
        "answer_revisions",
        "submissions",
        "grade_runs",
        "score_versions",
        "receipt_versions",
        "paper_versions",
        "omr_scan_submissions",
        "audit_events",
    ]
    counts: dict[str, int] = {}
    for tbl in tables:
        cnt = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar_one()
        counts[tbl] = int(cnt)
    return counts


def create_full_backup(
    db: Session,
    *,
    settings: Settings,
    teacher_id: int,
    label: str = "manual",
) -> BackupManifest:
    settings.backups_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    manifest_id = str(uuid.uuid4())
    archive_name = f"examguard_{label}_{stamp}_{manifest_id[:8]}.zip"
    archive_path = (settings.backups_dir / archive_name).resolve()

    alembic_ver = "unknown"
    with contextlib.suppress(Exception):
        alembic_ver = str(db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one())

    counts = _collect_record_counts(db)
    file_hashes: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        db_copy_path = tmp_dir / "examguard.db"

        src_conn = sqlite3.connect(settings.db_path)
        dst_conn = sqlite3.connect(db_copy_path)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        file_hashes["examguard.db"] = _sha256_file(db_copy_path)

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_copy_path, "examguard.db")

            for folder_name, base_dir in [
                ("sources", settings.sources_dir),
                ("assets", settings.assets_dir),
                ("receipts", settings.receipts_dir),
                ("paper", settings.paper_dir),
                ("scans", settings.scans_dir),
            ]:
                if base_dir.exists():
                    for p in base_dir.rglob("*"):
                        if p.is_file():
                            rel = f"{folder_name}/{p.relative_to(base_dir).as_posix()}"
                            file_hashes[rel] = _sha256_file(p)
                            zf.write(p, rel)

            manifest_payload = {
                "manifest_id": manifest_id,
                "created_at": now.isoformat(),
                "schema_version": alembic_ver,
                "record_counts": counts,
                "file_hashes": file_hashes,
            }
            zf.writestr("manifest.json", json.dumps(manifest_payload, indent=2, ensure_ascii=False))

    archive_sha = _sha256_file(archive_path)
    manifest = BackupManifest(
        id=manifest_id,
        created_at=now,
        schema_version=alembic_ver,
        sha256=archive_sha,
        location=archive_name,
        record_counts_json=json.dumps(counts),
        verified_at=now,
    )
    db.add(manifest)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="CREATE_BACKUP",
        target_type="backup",
        target_id=manifest_id,
        details={"location": archive_name, "sha256": archive_sha, "counts": counts},
    )
    db.commit()
    db.refresh(manifest)
    return manifest


def list_backups(db: Session) -> list[BackupManifest]:
    return list(
        db.execute(select(BackupManifest).order_by(BackupManifest.created_at.desc()))
        .scalars()
        .all()
    )


def verify_backup_archive(
    db: Session,
    *,
    settings: Settings,
    backup_id: str,
) -> VerifyRestoreReport:
    manifest = db.get(BackupManifest, backup_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản sao lưu.")

    archive_path = (settings.backups_dir / manifest.location).resolve()
    if not archive_path.is_relative_to(settings.backups_dir.resolve()) or not archive_path.is_file():
        raise HTTPException(status_code=404, detail="Tệp sao lưu không tồn tại trên ổ đĩa.")

    actual_zip_sha = _sha256_file(archive_path)
    if actual_zip_sha != manifest.sha256:
        raise HTTPException(
            status_code=400,
            detail="Mã băm SHA-256 của tệp sao lưu không khớp (nghi ngờ tệp bị hỏng).",
        )

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                if info.filename.startswith("/") or ".." in Path(info.filename).parts:
                    raise HTTPException(status_code=400, detail="Đường dẫn không hợp lệ trong sao lưu.")
            zf.extractall(tmp_dir)

        manifest_file = tmp_dir / "manifest.json"
        db_file = tmp_dir / "examguard.db"
        if not manifest_file.is_file() or not db_file.is_file():
            raise HTTPException(status_code=400, detail="Bản sao lưu thiếu manifest.json hoặc CSDL.")

        meta: dict[str, Any] = json.loads(manifest_file.read_text(encoding="utf-8"))
        hashes: dict[str, str] = meta.get("file_hashes", {})
        for rel, expected_sha in hashes.items():
            member_path = (tmp_dir / rel).resolve()
            if not member_path.is_relative_to(tmp_dir.resolve()) or not member_path.is_file():
                raise HTTPException(status_code=400, detail=f"Thiếu thành phần sao lưu: {rel}")
            if _sha256_file(member_path) != expected_sha:
                raise HTTPException(status_code=400, detail=f"Sai checksum SHA-256 tại: {rel}")

        conn = sqlite3.connect(db_file)
        try:
            res = conn.execute("PRAGMA quick_check;").fetchone()
            integrity_ok = bool(res and str(res[0]).lower() == "ok")
        finally:
            conn.close()

        if not integrity_ok:
            raise HTTPException(status_code=400, detail="Kiểm tra toàn vẹn SQLite trong sao lưu thất bại.")

        manifest.verified_at = datetime.now(UTC)
        db.commit()

        return VerifyRestoreReport(
            manifest_id=manifest.id,
            archive_name=manifest.location,
            schema_version=str(meta.get("schema_version", "unknown")),
            checksum_valid=True,
            sqlite_integrity_ok=True,
            record_counts=dict(meta.get("record_counts", {})),
            dry_run=True,
        )


def count_backups(db: Session) -> int:
    val = db.execute(select(func.count()).select_from(BackupManifest)).scalar_one()
    return int(val)


def restore_backup_archive(
    *,
    settings: Settings,
    archive_path: Path,
) -> VerifyRestoreReport:
    """Verify checksums & SQLite integrity, take a safety snapshot, and restore DB/sources/assets."""
    if not archive_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp sao lưu để khôi phục.")

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                if info.filename.startswith("/") or "\\" in info.filename or ".." in Path(info.filename).parts:
                    raise HTTPException(status_code=400, detail="Đường dẫn không hợp lệ trong tệp sao lưu.")
            zf.extractall(tmp_dir)

        manifest_file = tmp_dir / "manifest.json"
        db_file = tmp_dir / "examguard.db"
        if not manifest_file.is_file() or not db_file.is_file():
            raise HTTPException(status_code=400, detail="Tệp sao lưu không hợp lệ.")

        meta: dict[str, Any] = json.loads(manifest_file.read_text(encoding="utf-8"))
        hashes: dict[str, str] = meta.get("file_hashes", {})
        for rel, expected_sha in hashes.items():
            member = (tmp_dir / rel).resolve()
            if not member.is_relative_to(tmp_dir.resolve()) or not member.is_file():
                raise HTTPException(status_code=400, detail=f"Thiếu tệp trong bản sao lưu: {rel}")
            if _sha256_file(member) != expected_sha:
                raise HTTPException(status_code=400, detail=f"Checksum không khớp tại: {rel}")

        conn = sqlite3.connect(db_file)
        try:
            res = conn.execute("PRAGMA quick_check;").fetchone()
            if not (res and str(res[0]).lower() == "ok"):
                raise HTTPException(status_code=400, detail="SQLite trong bản sao lưu bị hỏng.")
        finally:
            conn.close()

        # Take pre-restore safety copy of existing DB if present
        if settings.db_path.exists():
            settings.backups_dir.mkdir(parents=True, exist_ok=True)
            safety_db = settings.backups_dir / f"pre_restore_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.db"
            s_conn = sqlite3.connect(settings.db_path)
            d_conn = sqlite3.connect(safety_db)
            try:
                s_conn.backup(d_conn)
            finally:
                d_conn.close()
                s_conn.close()

        # Atomic SQLite backup API into live db_path
        src_restore = sqlite3.connect(db_file)
        dst_restore = sqlite3.connect(settings.db_path)
        try:
            src_restore.backup(dst_restore)
        finally:
            dst_restore.close()
            src_restore.close()

        # Restore sources & assets non-destructively (add/update files)
        import shutil

        for folder, dest_root in [
            ("sources", settings.sources_dir),
            ("assets", settings.assets_dir),
            ("receipts", settings.receipts_dir),
            ("paper", settings.paper_dir),
            ("scans", settings.scans_dir),
        ]:
            extracted_dir = tmp_dir / folder
            if extracted_dir.is_dir():
                dest_root.mkdir(parents=True, exist_ok=True)
                for p in extracted_dir.rglob("*"):
                    if p.is_file():
                        target = dest_root / p.relative_to(extracted_dir)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, target)

        return VerifyRestoreReport(
            manifest_id=meta.get("manifest_id"),
            archive_name=archive_path.name,
            schema_version=str(meta.get("schema_version", "unknown")),
            checksum_valid=True,
            sqlite_integrity_ok=True,
            record_counts=dict(meta.get("record_counts", {})),
            dry_run=False,
        )
