"""Security primitives: local secret management, HMAC tokens, invite hashing, and rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_bearer_scheme = HTTPBearer(auto_error=False)


def load_or_create_server_secret(data_dir: Path) -> bytes:
    """Persist a cryptographically random local secret in ExamGuardData/.server_secret."""
    data_dir.mkdir(parents=True, exist_ok=True)
    secret_file = data_dir / ".server_secret"
    if secret_file.exists():
        raw = secret_file.read_text(encoding="utf-8").strip()
        if len(raw) >= 32:
            return bytes.fromhex(raw)
    new_secret = secrets.token_bytes(32)
    secret_file.write_text(new_secret.hex(), encoding="utf-8")
    return new_secret


def generate_invite_code(length: int = 6) -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))


def hash_secret_value(value: str, server_secret: bytes) -> str:
    """Hash invite codes or browser device keys at rest with HMAC-SHA256."""
    normalized = value.strip().upper()
    return hmac.new(server_secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_secret_value(value: str, stored_hash: str, server_secret: bytes) -> bool:
    computed = hash_secret_value(value, server_secret)
    return hmac.compare_digest(computed, stored_hash)


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_token(payload: dict[str, object], server_secret: bytes, ttl_seconds: int = 28800) -> str:
    now = int(time.time())
    body = {
        **payload,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = _b64_encode(raw)
    sig = hmac.new(server_secret, encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64_encode(sig)}"


def verify_token(token: str, server_secret: bytes) -> dict[str, object]:
    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ.",
        )
    encoded, sig_b64 = parts
    expected_sig = hmac.new(server_secret, encoded.encode("ascii"), hashlib.sha256).digest()
    try:
        actual_sig = _b64_decode(sig_b64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ.",
        ) from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chữ ký xác thực không khớp.",
        )

    try:
        payload = json.loads(_b64_decode(encoded).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không thể đọc phiên xác thực.",
        ) from exc

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại.",
        )
    return dict(payload)


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter to protect join/invite endpoints."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Thử sai quá nhiều lần. Vui lòng đợi 1 phút rồi thử lại.",
                )
            bucket.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)


@dataclass(frozen=True)
class TeacherPrincipal:
    teacher_id: int
    display_name: str


@dataclass(frozen=True)
class StudentPrincipal:
    attempt_id: str
    exam_id: str
    student_id: str
    session_id: str


def is_loopback_client(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def require_teacher(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TeacherPrincipal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu quyền giáo viên. Vui lòng đăng nhập trên máy chủ.",
        )
    secret: bytes = request.app.state.server_secret
    payload = verify_token(credentials.credentials, secret)
    if payload.get("role") != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản học sinh không có quyền truy cập chức năng giáo viên.",
        )
    teacher_id = payload.get("teacher_id")
    display_name = payload.get("display_name", "Giáo viên")
    if not isinstance(teacher_id, int):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token giáo viên lỗi.")
    return TeacherPrincipal(teacher_id=teacher_id, display_name=str(display_name))


def require_student(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> StudentPrincipal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu mã xác thực phiên học sinh.",
        )
    secret: bytes = request.app.state.server_secret
    payload = verify_token(credentials.credentials, secret)
    if payload.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token không thuộc phiên học sinh.",
        )
    attempt_id = payload.get("attempt_id")
    exam_id = payload.get("exam_id")
    student_id = payload.get("student_id")
    session_id = payload.get("session_id")
    if not all(isinstance(v, str) and v for v in (attempt_id, exam_id, student_id, session_id)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token học sinh lỗi.")
    return StudentPrincipal(
        attempt_id=str(attempt_id),
        exam_id=str(exam_id),
        student_id=str(student_id),
        session_id=str(session_id),
    )
