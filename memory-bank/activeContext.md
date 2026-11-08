# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: P4 — Realtime Monitoring & Security/Fairness (`EG-401`..`EG-408`).
- Objective: Triển khai WebSocket phòng thi `/ws/v1/room/{room_id}` có xác thực teacher/student, heartbeat & threshold grace configurable (3s/5s/15s), ghi nhận `visibilitychange`/`pagehide` trung lập (không kết luận gian lận tự động), `PresenceEvent` & `Incident`, bảng điều khiển giám sát thời gian thực cho giáo viên + xử lý `Mở lại` / `Gia hạn` / `Kết thúc` có audit, màn hình sự cố kỹ thuật cho học sinh và negative security tests.

## Last completed work

- 2026-11-08: Hoàn thành Phase P3 (`EG-301`..`EG-310` DONE). 20/20 pytest + 6/6 vitest + lint/typecheck/build PASS. Báo cáo tại `docs/phase-reports/PHASE_P3_REPORT.md`.