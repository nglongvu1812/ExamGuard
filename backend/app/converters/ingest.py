"""Secure file ingest with magic-byte check, zip-bomb & path-traversal guard, and SHA-256 storage."""

from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from pathlib import Path

from app.db.models import Asset, SourceDocument
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_ZIP_ENTRIES = 2000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_COMPRESSION_RATIO = 100.0

ALLOWED_IMAGE_EXTS: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".wmf": "image/x-wmf",
    ".emf": "image/x-emf",
}


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name.strip()
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in base)
    return cleaned[:200] or "exam_source.docx"


def _validate_zip_container_bytes(
    content: bytes,
    *,
    required_entries: set[str],
    format_label: str,
) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="Tệp đề thi trống.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Tệp đề thi vượt quá giới hạn 20 MB.")
    if not content.startswith(b"PK\x03\x04"):
        raise HTTPException(
            status_code=400,
            detail=f"Tệp không phải định dạng {format_label} hợp lệ.",
        )

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tệp nén {format_label} có quá nhiều thành phần bất thường.",
                )
            total_uncompressed = 0
            found_entries: set[str] = set()
            for info in infos:
                name = info.filename
                if name.startswith("/") or "\\" in name or ".." in Path(name).parts:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Phát hiện đường dẫn không an toàn (path traversal) trong tệp {format_label}.",
                    )
                if info.file_size > MAX_UNCOMPRESSED_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Thành phần trong tệp {format_label} vượt ngưỡng an toàn (zip bomb guard).",
                    )
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Tổng kích thước giải nén tệp {format_label} vượt ngưỡng an toàn.",
                    )
                if info.compress_size > 0 and (info.file_size / info.compress_size) > MAX_COMPRESSION_RATIO:
                    raise HTTPException(
                        status_code=400,
                        detail="Phát hiện tỷ lệ nén bất thường (nghi ngờ zip bomb).",
                    )
                if name in required_entries:
                    found_entries.add(name)

            missing = required_entries - found_entries
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tệp {format_label} thiếu thành phần chuẩn ({', '.join(sorted(missing))}).",
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail=f"Tệp {format_label} bị hỏng cấu trúc ZIP.") from exc


def validate_docx_bytes(content: bytes) -> None:
    _validate_zip_container_bytes(
        content,
        required_entries={"word/document.xml"},
        format_label="Word (.docx)",
    )


def validate_xlsx_bytes(content: bytes) -> None:
    _validate_zip_container_bytes(
        content,
        required_entries={"xl/workbook.xml"},
        format_label="Excel (.xlsx)",
    )


def validate_pdf_bytes(content: bytes) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="Tệp PDF trống.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Tệp PDF vượt quá giới hạn 20 MB.")
    if not content.lstrip(b"\xef\xbb\xbf\r\n ").startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Tệp không có chữ ký PDF (%PDF-) hợp lệ.")


def store_source_file(
    db: Session,
    *,
    sources_dir: Path,
    filename: str,
    content: bytes,
    kind: str,
) -> SourceDocument:
    ext = kind.lower().lstrip(".")
    if ext == "docx":
        validate_docx_bytes(content)
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == "pdf":
        validate_pdf_bytes(content)
        mime = "application/pdf"
    elif ext == "xlsx":
        validate_xlsx_bytes(content)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file đề .docx, .pdf hoặc .xlsx.")

    sha = hashlib.sha256(content).hexdigest()
    existing = db.execute(select(SourceDocument).where(SourceDocument.sha256 == sha)).scalar_one_or_none()
    if existing is not None:
        return existing

    sources_dir.mkdir(parents=True, exist_ok=True)
    relpath = f"{sha}.{ext}"
    target = (sources_dir / relpath).resolve()
    if not target.is_relative_to(sources_dir.resolve()):
        raise HTTPException(status_code=400, detail="Đường dẫn lưu trữ không hợp lệ.")
    target.write_bytes(content)

    doc = SourceDocument(
        id=str(uuid.uuid4()),
        sha256=sha,
        original_filename=sanitize_filename(filename),
        mime_type=mime,
        relpath=relpath,
        size_bytes=len(content),
    )
    db.add(doc)
    db.flush()
    return doc


def store_source_document(
    db: Session,
    *,
    sources_dir: Path,
    filename: str,
    content: bytes,
) -> SourceDocument:
    return store_source_file(
        db,
        sources_dir=sources_dir,
        filename=filename,
        content=content,
        kind="docx",
    )


def store_media_asset(
    db: Session,
    *,
    assets_dir: Path,
    filename: str,
    content: bytes,
) -> Asset:
    sha = hashlib.sha256(content).hexdigest()
    existing = db.get(Asset, sha)
    if existing is not None:
        return existing

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        ext = ".png"
    mime_type = ALLOWED_IMAGE_EXTS.get(ext, "application/octet-stream")

    subdir = assets_dir / sha[:2]
    subdir.mkdir(parents=True, exist_ok=True)
    relpath = f"{sha[:2]}/{sha}{ext}"
    target = (assets_dir / relpath).resolve()
    if not target.is_relative_to(assets_dir.resolve()):
        raise HTTPException(status_code=400, detail="Đường dẫn asset không hợp lệ.")
    target.write_bytes(content)

    asset = Asset(
        id=sha,
        mime_type=mime_type,
        byte_size=len(content),
        relpath=relpath,
    )
    db.add(asset)
    db.flush()
    return asset
