# Next Actions

1. Tạo Alembic migration `0005_monitoring_and_incidents.py` và ORM models `PresenceEvent`, `Incident`.
2. Xây dựng `monitoring_service.py` + `ws.py` WebSocket hub `/ws/v1/room/{exam_id}` (teacher & student auth, zero key leak, presence states `ACTIVE -> SUSPECTED -> DISCONNECTED -> LOCKED_PENDING_REVIEW`), API heartbeat, telemetry (`visibilitychange`/`pagehide`), kiểm tra quá hạn grace period và giáo viên xử lý sự cố (`unlock`, `extend_time`, `terminate`) ghi audit.
3. Xây dựng Teacher Live Monitoring Dashboard (`T6`) tích hợp vào phòng thi + Incident Drawer và Student Incident Screen (`S5`) tự động reconnect kèm backoff/jitter.
4. Viết `test_p4_monitoring.py` + kiểm thử UI Vitest + báo cáo `PHASE_P4_REPORT.md`.