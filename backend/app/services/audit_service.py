"""Append-only hash-chained audit event logging and verification."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.db.models import AuditEvent
from sqlalchemy import select
from sqlalchemy.orm import Session


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
    before_hash: str = "",
    after_hash: str = "",
) -> AuditEvent:
    """Append a tamper-evident audit event chained to the previous event hash."""
    prev_event = db.execute(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    ).scalar_one_or_none()
    prev_hash = prev_event.event_hash if prev_event else "GENESIS"

    created_at = datetime.now(UTC)
    details_json = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    canonical = "|".join(
        [
            prev_hash,
            actor_type,
            actor_id,
            action,
            target_type,
            target_id,
            details_json,
            before_hash,
            after_hash,
            created_at.isoformat(),
        ]
    )
    event_hash = _sha256_hex(canonical)

    event = AuditEvent(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details_json=details_json,
        before_hash=before_hash,
        after_hash=after_hash,
        prev_hash=prev_hash,
        event_hash=event_hash,
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def verify_audit_chain(db: Session) -> tuple[bool, int]:
    """Verify hash-chain consistency across all stored audit events."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
    expected_prev = "GENESIS"
    for ev in events:
        if ev.prev_hash != expected_prev:
            return False, ev.id
        ts = ev.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        canonical = "|".join(
            [
                ev.prev_hash,
                ev.actor_type,
                ev.actor_id,
                ev.action,
                ev.target_type,
                ev.target_id,
                ev.details_json,
                ev.before_hash,
                ev.after_hash,
                ts.isoformat(),
            ]
        )
        if _sha256_hex(canonical) != ev.event_hash:
            return False, ev.id
        expected_prev = ev.event_hash
    return True, len(events)
