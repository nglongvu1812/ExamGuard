# BÁO CÁO PHASE P4 — REALTIME MONITORING & SECURITY/FAIRNESS

## 5.1. Tổng quan

- **Tên Phase:** Phase P4 — Giám sát thời gian thực, Chính sách công bằng & Xử lý sự cố kỹ thuật (`Monitoring & Fairness`).
- **Mục tiêu:** Theo dõi trạng thái kết nối và tiến độ phòng thi theo thời gian thực qua WebSocket có xác thực theo phiên; tách rõ sự cố kỹ thuật (`network_lost`, `APP_HIDDEN`, `DISCONNECTED`) khỏi gian lận; cung cấp quy trình tạm khóa/mở lại/gia hạn/kết thúc có lý do và dấu vết kiểm tra (`AuditEvent`), cùng màn hình giải thích rõ ràng cho học sinh.
- **Danh sách Task:** `EG-401`..`EG-408`.
- **Trạng thái hoàn thành:**
  - `EG-401`, `EG-402`, `EG-403`, `EG-404`, `EG-405`, `EG-406`, `EG-408`: **DONE**.
  - `EG-407` (Ma trận thiết bị thật đa nền tảng Android/iOS): **REVIEW** (đã hoàn thành tài liệu `docs/MONITORING_MATRIX.md` và mô phỏng tự động; chờ pilot trên điện thoại thật cùng P7).

## 5.2. Chức năng đã triển khai

### Backend & Cơ sở dữ liệu
- **Đồng bộ luồng ghi SQLite & Audit Chain (`backend/app/db/locks.py`, `audit_service.py`):** Bổ sung `EXAM_WRITE_LOCK` (RLock) và `AUDIT_WRITE_LOCK` theo thứ tự phân cấp khóa chặt chẽ, bảo vệ `prev_hash` và `event_hash` khi có nhiều yêu cầu WebSocket/HTTP đồng thời.
- **Migration `0005_monitoring_and_incidents.py` & Models (`models.py`):**
  - Mở rộng `attempts` qua `batch_alter_table`: `presence_state`, `last_heartbeat_at`, `reconnect_count`, `hidden_event_count`.
  - Tạo bảng `presence_events` (ghi nhận `ACTIVE`, `HEARTBEAT_SUSPECTED`, `HEARTBEAT_TIMEOUT`, `RECONNECTED`, `APP_HIDDEN`, `PAGE_UNLOADED`, `NETWORK_LOST`, `CLIENT_RELOAD`, `LOCKED_PENDING_REVIEW`, `TEACHER_*`) và `incidents` (`OPEN`, `RESOLVED_UNLOCKED`, `RESOLVED_EXTENDED`, `RESOLVED_ENDED`).
- **Dịch vụ giám sát (`backend/app/services/monitoring_service.py`):**
  - Chính sách cấu hình linh hoạt trong `exam.policy_json` (`heartbeat_s`, `suspected_s`, `disconnect_s`, `lock_after_s`, `grace_submit_s`).
  - Đánh giá chuyển trạng thái non-punitive: `ACTIVE -> SUSPECTED -> DISCONNECTED -> LOCKED_PENDING_REVIEW` (chỉ chạy khi đề đang `RUNNING` và không `paused_at`); tự phục hồi `RECONNECTED -> ACTIVE` nếu chưa bị khóa.
  - Thao tác giáo viên có audit bắt buộc lý do: `lock_attempt_for_review`, `resolve_attempt_incident` (`unlock`, `extend_time` cộng `extra_time_s`, `terminate` đóng bài và niêm phong ngay `Submission(submission_mode="teacher_terminate_review")` để không mất bài đã ACK).
  - `refresh_student_token` kiểm tra lại `session_id` và `DeviceBinding` còn hiệu lực trước khi gia hạn token.
  - Đưa cơ chế xoay `attempt.session_id` ngay lập tức vào `room_service.reset_attempt_device` để vô hiệu hóa đồng thời cả token HTTP và WebSocket cũ.
- **WebSocket & Monitoring APIs (`ws.py`, `monitoring.py`, `main.py`, `rooms.py`, `exams.py`):**
  - WebSocket `/ws/v1/room/{exam_id}`: xác thực token ngay trước `accept()`, từ chối mã `1008` nếu sai token/sai `exam_id`/stale `session_id`/chưa được duyệt. Phía học sinh chỉ nhận trạng thái phòng thi và bản thân, **tuyệt đối không rò rỉ đáp án hoặc thông tin bạn cùng lớp**.
  - REST APIs: `GET /api/v1/monitoring/exams/{exam_id}`, `PATCH /policy`, `GET .../timeline`, `POST .../lock`, `POST .../resolve`, `POST /attempts/{id}/heartbeat`, `POST /attempts/{id}/events`, `POST /attempts/{id}/refresh-token`.
  - Vòng lặp nền `_presence_sweeper` (mỗi 2s trong `lifespan`) tự động quét phòng đang thi và đẩy snapshot tới teacher WebSocket; hủy sạch khi shutdown.

### Frontend (`T4` / `T6` / `S4` / `S5`)
- **Màn hình Giáo viên (`WaitingRoomPage.tsx`):**
  - Cấu hình ngưỡng giám sát ở bước tạo phòng và chỉnh sửa trực tiếp khi phòng đang mở.
  - Dải thống kê trực tiếp (Sĩ số, Đang làm, Đã nộp, Chờ duyệt, Mất kết nối, Tạm khóa / Sự cố) kết hợp WebSocket trực tiếp + HTTP polling fallback 3s.
  - Phân biệt rõ trạng thái bằng **Màu + Chữ + Icon** (`Ổn định`, `Tín hiệu yếu`, `Mất kết nối`, `Rời màn hình (K) · Cần xác minh`); **không tự gán nhãn `GIAN LẬN`**.
  - Ngăn kéo `Hồ sơ sự cố & Nhật ký tín hiệu` hiển thị timeline chi tiết kèm 3 nút hành động xác nhận (`Mở lại làm bài`, `Gia hạn (+phút)`, `Kết thúc & Niêm phong`).
- **Màn hình Học sinh (`StudentExamPage.tsx`, `StudentJoinShell.tsx`):**
  - Kết nối WebSocket tự nối lại theo **exponential backoff + jitter**; phát heartbeat theo `heartbeat_s`, fallback HTTP heartbeat khi WS rớt; bắt `visibilitychange`, `pagehide`, `offline`/`online`.
  - Banner mất kết nối LAN (S5) giải thích các đáp án có dấu `Đã lưu` đã an toàn trên máy chủ và giữ các lựa chọn chưa đồng bộ trong `localStorage`.
  - Màn hình khóa kỹ thuật `LOCKED_PENDING_REVIEW` / `ENDED_WITH_REVIEW` giải thích lý do rõ ràng, hiển thị `server_revision`, giờ máy chủ và nút kiểm tra trạng thái mở lại mà **không tự reset bài thi hay đồng hồ**.

## 5.3. Danh sách file

- **Tạo mới:**
  - `backend/app/db/locks.py`
  - `backend/alembic/versions/0005_monitoring_and_incidents.py`
  - `backend/app/services/monitoring_service.py`
  - `backend/app/api/monitoring.py`
  - `backend/app/api/ws.py`
  - `backend/tests/test_p4_monitoring.py`
  - `docs/MONITORING_MATRIX.md`
  - `docs/phase-reports/PHASE_P4_REPORT.md`
- **Chỉnh sửa:**
  - `backend/app/db/models.py`, `backend/app/services/audit_service.py`, `backend/app/services/answer_service.py`, `backend/app/services/exam_service.py`, `backend/app/services/room_service.py`
  - `backend/app/api/rooms.py`, `backend/app/api/exams.py`, `backend/app/main.py`
  - `backend/tests/test_p1_roster_and_rooms.py`, `backend/tests/test_p3_exam_engine.py`
  - `frontend/src/api/client.ts`, `frontend/src/pages/teacher/WaitingRoomPage.tsx`, `frontend/src/pages/student/StudentExamPage.tsx`, `frontend/src/pages/student/StudentJoinShell.tsx`, `frontend/src/App.test.tsx`

## 5.4. Kiểm thử

- Chạy `powershell -ExecutionPolicy Bypass -File tools\verify.ps1`:
  - `ruff check`: **PASS** (All checks passed)
  - `mypy --config-file backend/pyproject.toml` (+ kiểm bổ sung trên cả `backend/app` và `backend/tests`): **PASS** (0 issues across 37 files)
  - `pytest -v`: **PASS** (`22/22` passed — gồm `test_websocket_auth_rejection_cross_scope_and_zero_key_leak` và `test_grace_thresholds_auto_lock_and_teacher_resolution_flows` + toàn bộ regression P0–P3 & Alembic `upgrade head -> downgrade base -> upgrade head`)
  - `eslint .` + `tsc -b --noEmit`: **PASS**
  - `vitest run`: **PASS** (`8/8` passed — gồm T6 Monitoring & Incident Drawer + S5 Technical Lock screen)
  - `vite build`: **PASS** (build production static bundle không dùng CDN ngoài).
- **Lỗi đã phát hiện & xử lý trong lượt:** Sửa `NameError`/`no-redef` biến `snap` trong `ws.py`; sửa regex case-insensitive trong test T6 tránh match nhầm chữ `"gian lận"` nằm trong câu tuyên bố miễn trừ trách nhiệm trung lập.

## 5.5. Vấn đề và giới hạn

- **Rủi ro HTTP LAN & Safari nền:** Nếu phòng thi chạy HTTP thuần qua Wi-Fi lớp học, dữ liệu WebSocket không mã hóa TLS; đồng thời Safari iOS khi tắt sáng hoặc thu nhỏ tab sẽ tạm dừng WS nền (đã xử lý bằng ngưỡng grace có thể điều chỉnh và khuyến nghị trong `docs/MONITORING_MATRIX.md`).
- **Chưa chạy ma trận thực nghiệm trên 3 điện thoại vật lý khác nhau:** Sẽ được kiểm chứng bổ sung khi có phần cứng AP/điện thoại thực tế trong Phase P7.

## 5.6. Kết luận

- **Tiêu chí nghiệm thu đã đạt:** Xác thực WebSocket đa vai trò, chống truy cập chéo, không rò rỉ đáp án/dữ liệu học sinh khác, heartbeat + grace có thể cấu hình, ghi nhận tín hiệu rời trang trung lập, khóa/mở lại/gia hạn/kết thúc có audit và bảo toàn bài làm đã ACK, S5 & T6 UI hoàn chỉnh.
- **Trạng thái cuối cùng:** **PASS** (các bài kiểm tra phần mềm/tích hợp đạt 100%; `EG-407` giữ `REVIEW` đợi phần cứng pilot).
- **Bước tiếp theo:** Tự động chuyển sang **Phase P5 — Scoring, Audit, Publication, Receipts (`EG-501`..`EG-510`)**.
