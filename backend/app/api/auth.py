"""Authentication endpoints for local teacher console."""

from __future__ import annotations

from typing import Any

from app.api.deps import get_db
from app.db.models import TeacherProfile
from app.security.auth import (
    SlidingWindowRateLimiter,
    TeacherPrincipal,
    is_loopback_client,
    require_teacher,
    sign_token,
)
from app.services.audit_service import record_audit_event
from app.services.roster_service import (
    DEFAULT_TEACHER_PIN,
    ensure_default_teacher,
    update_teacher_pin,
    verify_teacher_pin,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class TeacherSessionResponse(BaseModel):
    token: str
    teacher_id: int
    display_name: str
    role: str


class TeacherLoginRequest(BaseModel):
    pin: str = DEFAULT_TEACHER_PIN


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str


@router.post("/teacher/login", response_model=TeacherSessionResponse)
def teacher_login(
    payload: TeacherLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TeacherSessionResponse:
    """Authenticate a teacher session via PIN, strictly respecting LAN access boundaries."""
    settings = request.app.state.settings
    if not is_loopback_client(request) and not settings.allow_lan_teacher_console:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quản trị giáo viên qua mạng LAN đã bị khóa. Vui lòng thao tác trực tiếp trên máy chủ cục bộ.",
        )

    client_ip = request.client.host if request.client else "unknown"
    limiter: SlidingWindowRateLimiter = getattr(
        request.app.state, "join_limiter", SlidingWindowRateLimiter(max_attempts=10, window_seconds=60)
    )
    limiter.check_and_record(f"teacher_pin:{client_ip}")

    teacher = ensure_default_teacher(db)
    secret: bytes = request.app.state.server_secret
    if not verify_teacher_pin(teacher, payload.pin, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã PIN quản trị không chính xác.",
        )

    limiter.reset(f"teacher_pin:{client_ip}")

    token = sign_token(
        {
            "role": "teacher",
            "teacher_id": teacher.id,
            "display_name": teacher.display_name,
        },
        secret,
        ttl_seconds=28800,
    )
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher.id),
        action="TEACHER_LOGIN",
        target_type="teacher_profile",
        target_id=str(teacher.id),
        details={"client_ip": client_ip, "is_loopback": is_loopback_client(request)},
    )
    return TeacherSessionResponse(
        token=token,
        teacher_id=teacher.id,
        display_name=teacher.display_name,
        role="teacher",
    )


@router.post("/teacher/local-session", response_model=TeacherSessionResponse)
def create_local_teacher_session(
    request: Request,
    payload: TeacherLoginRequest | None = None,
    db: Session = Depends(get_db),
) -> TeacherSessionResponse:
    """Issue a TeacherToken only to requests originating from the host loopback interface, validating PIN."""
    if not is_loopback_client(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Giao diện quản trị giáo viên chỉ được phép đăng nhập trực tiếp trên máy chủ cục bộ.",
        )
    pin = payload.pin if (payload and payload.pin) else DEFAULT_TEACHER_PIN
    teacher = ensure_default_teacher(db)
    secret: bytes = request.app.state.server_secret
    if not verify_teacher_pin(teacher, pin, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã PIN quản trị không chính xác.",
        )
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


@router.post("/teacher/change-pin")
def change_teacher_pin(
    payload: ChangePinRequest,
    request: Request,
    teacher_principal: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Change the Teacher console access PIN."""
    if len(payload.new_pin.strip()) < 4:
        raise HTTPException(status_code=400, detail="Mã PIN mới phải có ít nhất 4 ký tự.")
    teacher = db.get(TeacherProfile, teacher_principal.teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ giáo viên.")
    secret: bytes = request.app.state.server_secret
    if not verify_teacher_pin(teacher, payload.current_pin, secret):
        raise HTTPException(status_code=400, detail="Mã PIN hiện tại không đúng.")
    update_teacher_pin(db, teacher, payload.new_pin.strip(), secret)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher.id),
        action="CHANGE_TEACHER_PIN",
        target_type="teacher_profile",
        target_id=str(teacher.id),
    )
    return {"status": "ok", "message": "Đã đổi mã PIN giáo viên thành công."}
