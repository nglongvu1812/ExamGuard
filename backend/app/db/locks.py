"""Process-local synchronization locks ordered cleanly to avoid SQLite race conditions."""

from __future__ import annotations

import threading

# Lock hierarchy: EXAM_WRITE_LOCK -> AUDIT_WRITE_LOCK (never acquire in reverse order)
EXAM_WRITE_LOCK = threading.RLock()
AUDIT_WRITE_LOCK = threading.Lock()
