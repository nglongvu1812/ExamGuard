"""Authentication endpoints for local teacher console."""

from __future__ import annotations

from app.api.deps import get_db
from app.security.auth import is_loopback_client, sign_token
from app.services.roster_service import ensure_default_teacher
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TeacherSessionResponse(BaseModel):
    token: str
    teacher_id: int
    display_name: str
    role: str


@router.post("/teacher/local-session", response_model=TeacherSessionResponse)
def create_local_teacher_session(
    request: Request,
    db: Session = Depends(get_db),
) -> TeacherSessionResponse:
    """Issue a TeacherToken only to requests originating from the host loopback interface."""
    if not is_loopback_client(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Giao diện quản trị giáo viên chỉ được phép đăng nhập trực tiếp trên máy chủ cục bộ.",
        )
    teacher = ensure_default_teacher(db)
    secret: bytes = request.app.state.server_secret
    token = sign_token(
        {
            "role": "teacher",
            "teacher_id": teacher.id,
            "display_name": teacher.display_name,
        },
        secret,
        ttl_seconds=28800,
    )
    return TeacherSessionResponse(
        token=token,
        teacher_id=teacher.id,
        display_name=teacher.display_name,
        role="teacher",
    )
