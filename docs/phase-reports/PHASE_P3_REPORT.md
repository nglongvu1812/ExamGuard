# Báo Cáo Hoàn Thành Phase P3 — Exam Engine, Timer & Answer Integrity

## 5.1. Tổng quan
- **Tên Phase:** P3 — Exam Engine, Timer, Answer Integrity (`EG-301`..`EG-310`)
- **Mục tiêu:** Triển khai toàn bộ lõi vận hành phòng thi LAN: cấu hình kỳ thi từ ngân hàng câu hỏi đã duyệt, trộn câu hỏi & phương án xác định theo seed bảo toàn `option_id`, máy trạng thái kỳ thi chặt chẽ (`READY -> WAITING -> RUNNING -> CLOSED`), đồng hồ đếm ngược phía server + tạm dừng/tiếp tục cộng bù giờ, lưu bài commit-before-ACK idempotent, đồng bộ phục hồi sau restart server/mất kết nối, nộp bài nguyên tử bất biến, và sao lưu/khôi phục SQLite nhất quán kèm kiểm thử dry-run.
- **Danh sách Task & Trạng thái:**
  - `EG-301`: API & UI cấu hình đề thi (`T4`) + kiểm thử chặn chuyển trạng thái sai (`409`) — **DONE**
  - `EG-302`: Thuật toán hoán vị theo `seed` (`ExamPermutation`) giữ nguyên `option_id` để chấm chính xác — **DONE**
  - `EG-303`: Vòng đời phòng thi `WAITING -> RUNNING -> CLOSED`, server timer, `pause` có lý do & `resume` bù giờ — **DONE**
  - `EG-304`: Giao diện thi học sinh mobile responsive (`S4`, `S6`), navigator, hiển thị trạng thái lưu trung thực (`Đang lưu...` / `Đã lưu #N` / `Chờ đồng bộ`) — **DONE**
  - `EG-305`: Ghi đáp án transactional (`AnswerRevision`), idempotency key chống ghi trùng, commit DB trước khi trả ACK — **DONE**
  - `EG-306`: Endpoint `/sync` và hàng đợi pending local đồng bộ lại đáp án chuẩn từ server sau mất kết nối — **DONE**
  - `EG-307`: Nộp bài atomic & idempotent tạo `Submission` kèm `snapshot_hash` SHA-256 — **DONE**
  - `EG-308`: Sao lưu nóng SQLite (`sqlite3.Connection.backup`) + `assets/sources` + `manifest.json` SHA-256 & kiểm thử khôi phục (`SettingsBackupPage`) — **DONE**
  - `EG-309`: Kiểm thử tranh chấp đồng thời (`ThreadPoolExecutor` save/submit/close race) — **DONE**
  - `EG-310`: Mô phỏng đầy đủ 5 học sinh giả lập qua quy trình: cấu hình -> duyệt -> làm bài -> pause/resume -> khởi động lại server -> nộp bài & không rò đáp án — **DONE**

## 5.2. Chức năng đã triển khai
- **Backend:**
  - `app/services/exam_service.py`: Máy trạng thái `ALLOWED_EXAM_TRANSITIONS`, `ensure_student_permutation`, `compute_remaining_seconds`, `start_exam_session`, `pause_exam_session`, `resume_exam_session`, `close_exam_session` (tự động đóng gói `Submission` `teacher_close_auto` cho thí sinh chưa nộp).
  - `app/services/answer_service.py`: `get_student_paper_payload` (loại bỏ hoàn toàn đáp án chuẩn và seed), `save_answer_revision` (kiểm tra deadline phía server, khóa `_ANSWER_WRITE_LOCK` + unique index `(attempt_id, idempotency_key)` chống race), `get_canonical_sync_state`, `submit_student_attempt`.
  - `app/services/backup_service.py`: `create_full_backup`, `verify_backup_archive` (dry-run), `restore_backup_archive` (tạo bản sao phòng ngừa trước khi ghi đè).
  - `app/api/exams.py` & `app/api/rooms.py`: Đầy đủ endpoint cấu hình, điều khiển kỳ thi, `/attempts/me/paper`, `/attempts/{id}/answers`, `/attempts/{id}/sync`, `/attempts/{id}/submit`, `/system/backups`.
- **Database (`alembic/versions/0004_exam_engine_and_answers.py`):**
  - Mở rộng `exams` và `attempts`; tạo mới `exam_questions`, `exam_permutations`, `answer_revisions`, `submissions`, `backup_manifests`.
- **Frontend:**
  - `src/pages/teacher/WaitingRoomPage.tsx`: Tích hợp 4 bước tạo bài kiểm tra, chọn câu hỏi ngân hàng, bật/tắt trộn đề, danh sách mã mời, điều khiển `Bắt đầu`/`Tạm dừng`/`Tiếp tục`/`Đóng phòng` kèm modal xác nhận và bảng tiến độ thí sinh.
  - `src/pages/student/StudentExamPage.tsx`: Màn hình thi di động (`S4`/`S6`), đồng hồ server sticky, hàng đợi pending trong `localStorage`, render KaTeX + zoom ảnh, modal xác nhận nộp bài.
  - `src/pages/teacher/SettingsBackupPage.tsx`: Tạo bản sao lưu và kiểm thử khôi phục dry-run.

## 5.3. Danh sách file thay đổi chính
- Tạo mới: `backend/alembic/versions/0004_exam_engine_and_answers.py`, `backend/app/services/{exam_service,answer_service,backup_service}.py`, `backend/app/api/exams.py`, `backend/tests/test_p3_exam_engine.py`, `frontend/src/pages/student/StudentExamPage.tsx`, `frontend/src/pages/teacher/SettingsBackupPage.tsx`.
- Chỉnh sửa: `backend/app/db/models.py`, `backend/app/api/rooms.py`, `backend/app/main.py`, `frontend/src/{App.tsx,App.test.tsx,api/client.ts}`, `frontend/src/pages/student/StudentJoinShell.tsx`, `frontend/src/pages/teacher/WaitingRoomPage.tsx`.

## 5.4. Kiểm thử
- `ruff check`: **PASS** (0 lỗi).
- `mypy`: **PASS** (28 file nguồn backend, 0 lỗi).
- `pytest -v`: **PASS** (20/20 tests — bổ sung 4 kịch bản P3: state transitions & permutation, luồng 5 HS + pause/resume + restart app giữ nguyên ACKed answers + clock tamper bị từ chối + 0 key leak, ThreadPoolExecutor race 6 luồng save / 5 luồng submit -> 1 submission, backup dry-run + restore sau khi xóa DB).
- `eslint` + `tsc -b --noEmit` + `vitest` (6/6 tests) + `vite build`: **PASS**.
- **Lỗi phát hiện & đã sửa trong P3:** Trong test `ThreadPoolExecutor` submit đồng thời 5 luồng, `record_audit_event()` gọi `db.flush()` trước `db.commit()` làm `IntegrityError` phát sinh sớm trước khối `try/except`; đã khắc phục bằng cách bọc `db.add(submission) -> db.flush() -> record_audit_event -> db.commit()` gọn trong `_ANSWER_WRITE_LOCK` + `try/except IntegrityError`.

## 5.5. Vấn đề và giới hạn
- Bài kiểm thử restart và concurrent được thực hiện ở mức tích hợp tự động trên tiến trình đơn Windows; kiểm thử ngắt nguồn đột ngột hoặc lỗi ổ đĩa vật lý bổ sung sẽ thực hiện trong checklist Phase P7.
- Đồng bộ thời gian thực qua WebSocket và cảnh báo `visibilitychange` / grace timeout thuộc phạm vi Phase P4 ngay kế tiếp.

## 5.6. Kết luận
- **Tiêu chí nghiệm thu đã đạt:** Toàn bộ Gate P3 (tạo đề, trộn đề bảo toàn option ID, vòng đời phòng thi, lưu đáp án không mất sau restart, double submit an toàn, client clock giả mạo không qua mặt được server, không rò đáp án trong API học sinh, backup/restore hoạt động).
- **Trạng thái cuối cùng:** **PASS**
- **Nhiệm vụ tiếp theo:** Tự động chuyển sang **Phase P4 — Realtime Monitoring & Security/Fairness (`EG-401`..`EG-408`)**.
