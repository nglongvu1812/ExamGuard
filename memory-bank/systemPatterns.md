# System Patterns — invariants to remember

1. **Authoritative Server:** client state is view, not truth for time/score/permissions.
2. **Idempotent Writes:** every meaningful save/submit has stable request ID and transaction ACK semantics.
3. **Version Instead of Mutation:** submissions, key/rubric, grades and receipts are versioned/snapshotted.
4. **Human-in-the-Loop Import:** source fidelity > AI inference; review unknowns.
5. **Least Privilege:** student token only accesses own attempt; teacher admin only privileged surface.
6. **Deferred Publication:** `CLOSED` ≠ published; only `PUBLISHED` allows key/receipt.
7. **Graceful Failures:** reconnect/lock is technical state; suspected != guilty.
8. **Offline Bundled:** static/fonts/math/icons and services on same device/LAN.
9. **No PII in Git:** synthetic fixtures, minimal roster fields; backup/restore controlled.
10. **Measure Before Claim:** performance, security, accuracy have test evidence, not marketing promises.
