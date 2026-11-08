"""Secure offline asset serving endpoint (images stored by SHA-256)."""

from __future__ import annotations

from app.api.deps import get_db
from app.db.models import Asset
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("/{asset_id}")
def get_asset(
    asset_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> FileResponse:
    if not asset_id.isalnum() or len(asset_id) != 64:
        raise HTTPException(status_code=400, detail="Mã asset không hợp lệ.")
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp phương tiện.")

    assets_dir = request.app.state.settings.assets_dir.resolve()
    file_path = (assets_dir / asset.relpath).resolve()
    if not file_path.is_relative_to(assets_dir) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Tệp phương tiện không tồn tại.")

    return FileResponse(
        file_path,
        media_type=asset.mime_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=86400, immutable",
        },
    )
