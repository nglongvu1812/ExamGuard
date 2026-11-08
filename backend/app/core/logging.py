"""Structured local logging with rotation and PII/secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r'(?i)("?(?:token|secret|password|invite_code|authorization)"?\s*[:=]\s*"?)([^",\s}]+)'
        ),
        r"\1[REDACTED]",
    ),
)


def redact_text(value: str) -> str:
    """Redact potential tokens, invite codes, and passwords from log messages."""
    sanitized = value
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RedactingJsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON with UTC timestamp and redaction."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(logs_dir: Path, level: str = "INFO") -> None:
    """Configure rotating file handler and console handler with redaction."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "examguard.log"

    root_logger = logging.getLogger("examguard")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()

    formatter = RedactingJsonFormatter()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
