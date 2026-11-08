# Báo Cáo Hoàn Thành Phase P1 — Classrooms & Roster Identity

## 1. Tổng quan
- **Tên Phase:** P1 — Classrooms & Roster Identity (`EG-101`..`EG-107`)
- **Mục tiêu:** Triển khai quản lý lớp học lâu dài, định danh học sinh không cần tài khoản cloud (UUID ổn định), import CSV/XLSX có bước kiểm tra trước (dry-run) và xử lý trùng lặp, cấp mã mời cá nhân băm HMAC-SHA256 kèm rate-limit, quy trình phòng chờ + duyệt vào thi + ràng buộc 1 attempt/học sinh + đặt lại thiết bị có audit log, và kiểm thử cô lập dữ liệu học sinh.
- **Danh sách Task:**
  - `EG-101`: Classroom/student CRUD service/API/DB + tests — **DONE**
  - `EG-102`: Import CSV/XLSX preview, dry-run phát hiện trùng, xử lý file hỏng — **DONE**
  - `EG-103`: Teacher Roster UI (`/classes`) tìm kiếm, sửa tên giữ UUID, lưu trữ, import wizard — **DONE**
  - `EG-104`: Mã mời ngẫu nhiên băm HMAC-SHA256 tại rest, TTL hết hạn & rate limiting (`429`) — **DONE**
  - `EG-105`: Luồng học sinh vào phòng chờ (`PENDING_APPROVAL`) + Teacher approval UI (`WaitingRoomPage`) + race test — **DONE**
  - `EG-106`: Ràng buộc 1 active attempt/student (`UniqueConstraint`), browser binding best-effort & teacher reset/rebind có audit chain — **DONE**
  - `EG-107`: Negative security tests (cô lập truy cập chéo giữa học sinh, chặn học sinh gọi API giáo viên, chặn unauthenticated) — **DONE**

## 2. Chức năng đã triển khai
- **Backend:**
  - `app/security/auth.py`: Tạo và lưu `.server_secret` cục bộ, HMAC-SHA256 token cho Teacher (loopback-only local session) & Student (`attempt_id` scoped), `SlidingWindowRateLimiter` (10 lần/60s), băm `invite_code` và `browser_key`.
  - `app/db/models.py` + `alembic/versions/0002_roster_and_invites.py`: Bảng `classrooms`, `students`, `class_memberships`, `exams`, `student_invites`, `attempts` (ràng buộc `uq_attempt_exam_student`), `device_bindings`, `audit_events`.
  - `app/services/audit_service.py`: Ghi nhật ký append-only băm chuỗi SHA-256 (`record_audit_event`, `verify_audit_chain`).
  - `app/services/roster_service.py`: CRUD lớp/học sinh (sửa tên giữ nguyên `Student.id`), import CSV/XLSX dry-run + commit theo chính sách (`skip`, `update_name`, `fail`).
  - `app/services/room_service.py`: Mở phòng chờ, phát mã mời 1 lần (chỉ lưu hash), `join_exam_room`, `approve_attempt`, `approve_all_pending`, `reset_attempt_device` (bắt buộc nhập lý do).
  - `app/api/auth.py`, `app/api/roster.py`, `app/api/rooms.py`: Đầy đủ DTO Pydantic và kiểm tra quyền server-side tại mọi route.
- **Frontend:**
  - `src/pages/teacher/ClassesPage.tsx`: Quản lý lớp, tìm kiếm, sửa tên giữ nguyên mã/UUID, lưu trữ, dry-run import Excel/CSV trực quan.
  - `src/pages/teacher/WaitingRoomPage.tsx`: Tạo phòng, hiển thị mã mời 1 lần, duyệt từng người / duyệt tất cả, đặt lại thiết bị kèm lý do.
  - `src/pages/student/StudentJoinShell.tsx`: Gắn `browser_key` cục bộ, gửi yêu cầu vào phòng, tự động poll trạng thái `PENDING_APPROVAL` -> `READY`.

## 3. Kiểm thử
- `ruff check`: **PASS** (0 lỗi).
- `mypy`: **PASS** (17 files, 0 lỗi).
- `pytest -v`: **PASS** (11/11 tests — bao gồm test import 40 HS XLSX + sửa 2 tên giữ nguyên sĩ số 40, chặn thiết bị thứ 2 cùng học sinh với `409`, teacher reset thiết bị có audit chain hợp lệ, rate limit `429`, invite hết hạn `401`, concurrent race 4 luồng chỉ tạo 1 attempt, cross-student `403`, student gọi API teacher `403`).
- `eslint` + `tsc` + `vitest` (4/4 tests) + `vite build`: **PASS**.

## 4. Vấn đề và giới hạn
- Device binding dựa trên `localStorage` của trình duyệt mang tính best-effort theo ADR-004 (học sinh xóa dữ liệu trình duyệt hoặc đổi trình duyệt cần giáo viên đối chiếu khi duyệt).

## 5. Kết luận
- **Trạng thái cuối cùng:** **PASS** (Đạt toàn bộ Gate P1).
- **Chuyển tiếp tự động:** Chuyển sang **Phase P2 — Converter v1 Word & Question Bank (`EG-201`..`EG-209`)**.
