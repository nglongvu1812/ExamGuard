# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: Toàn bộ Phase P0–P7 đã hoàn thành triển khai và nghiệm thu (`v0.1.0-beta.1`).
- Objective: Duy trì trạng thái ổn định của toàn bộ 33 bài kiểm thử tự động, gói phát hành Portable Windows `ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.55 MB, SHA-256 xác thực), kết quả đo tải dồn dập 45 học sinh ảo (3 lượt lặp, p95=727.9ms, 0 mất ACK), và trọn bộ tài liệu vận hành ngoại tuyến. Sẵn sàng cho giai đoạn thử nghiệm thực địa (`Field Pilot`).

## Last completed work

- 2026-11-08: Tinh chỉnh phòng chờ, xóa phòng thi, bảo toàn mã học sinh và cấu hình favicon:
  - Backend:
    - Bổ sung Alembic migration `0008_student_invite_plaintext_code.py` và cột `invite_code` trên bảng `student_invites`.
    - Cập nhật `create_waiting_room_session` và `_transition_to_waiting_and_issue_invites` lưu mã dự thi dạng bản rõ để giáo viên có thể tra cứu và hiển thị lại bất cứ khi nào cần.
    - Bổ sung endpoint `GET /api/v1/rooms/{exam_id}/invites` trả về danh sách mã tham gia còn hiệu lực cho phòng thi.
    - Bổ sung `delete_exam_session` và endpoint `DELETE /api/v1/exams/{exam_id}` xóa cascade toàn bộ dữ liệu phụ thuộc (bài làm, thiết bị, sự cố, bản ghi phúc khảo, điểm số, bài nộp) kèm ghi nhật ký audit.
    - Cung cấp định tuyến `/favicon.ico` và `/favicon.svg` tường minh trên FastAPI backend.
  - Frontend:
    - Loại bỏ hoàn toàn thanh "Phòng thi gần đây" trên giao diện phòng chờ để loại trừ xung đột giao diện và tránh kẹt phòng cũ.
    - Sửa thuật toán chọn phòng tự động (`loadBase`): ưu tiên phòng đang mở (`WAITING`/`RUNNING`), không giữ phòng đã hủy (`CANCELLED`).
    - Tự động nạp mã dự thi (`roomApi.getRoomInvites`) khi phòng ở trạng thái `WAITING`, hiển thị bảng mã cấp cho học sinh ngay khi mở phòng.
    - Bổ sung nút màu đỏ "Xóa phòng thi" (có hộp thoại xác nhận an toàn) cho mọi phòng chờ, phòng đã hủy hoặc phòng đã kết thúc.
    - Cập nhật `index.html` với cache-busting query `?v=2` cho icon/favicon.
  - Đóng gói & Phát hành:
    - Toàn bộ pipeline `verify.ps1` (ruff, mypy, 34 bài pytest, eslint, tsc, 11 bài vitest, vite build) PASS 100%.
    - Đóng gói lại thành công `ExamGuard.exe` và `dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip`.


- 2026-11-08: Sửa lỗi xung đột phòng chờ và hỗ trợ giáo viên vào lại phòng chờ:
  - Backend:
    - Bổ sung `cancel_exam_session` và endpoint `POST /api/v1/exams/{exam_id}/cancel`.
    - Triển khai chính sách một phòng chờ hoạt động (`Single Active Room Policy`): tự động hủy phòng chờ cũ ở trạng thái `WAITING` của lớp khi giáo viên mở phòng chờ mới (ghi nhật ký audit rõ ràng).
    - Thêm endpoint `GET /api/v1/exams/active` trả về phiên thi đang hoạt động (`WAITING` hoặc `RUNNING`).
  - Frontend:
    - `WaitingRoomPage`: Hỗ trợ route `/exams/:examId/waiting`, tự động phục hồi phòng thi đang hoạt động từ `getActiveExam()`, bổ sung nút "Hủy phòng chờ này" (có xác nhận) giúp giáo viên chủ động xóa phòng chờ cũ.
    - `DashboardPage`: Bổ sung banner nổi bật hiển thị phòng thi/phòng chờ đang hoạt động kèm mã phòng và nút 1-click "Vào lại phòng thi" giúp giáo viên quay lại ngay lập tức khi vô tình rời trang.
    - `TeacherLayout`: Cập nhật menu trực quan và linh hoạt.
  - Kiểm thử & Chất lượng:
    - Bổ sung bài kiểm thử `test_waiting_room_cancellation_and_active_exam_endpoint` trong `test_p1_roster_and_rooms.py`.
    - Chạy toàn bộ pipeline xác minh `tools/verify.ps1` (ruff, mypy, 34 bài pytest, eslint, tsc, 11 bài vitest, vite build): tất cả PASS.


- 2026-11-08: Hoàn thành Phase P7 (`EG-701`..`EG-712`).
  - Đóng gói PyInstaller onedir `ExamGuard.exe` (17.01 MB), bộ khởi chạy `ExamGuard.bat`, các tệp mẫu sẵn có (`samples/`), và nén bản phát hành portable `dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.66 MB, SHA-256: `82c0803b96feb0cdcd3e5e8aef7419bf207f46139db70bade8f9ab5a7fb1edec`).
  - Khởi chạy lạnh thành công trên Microsoft Windows 11 Pro Build 28000; kiểm toán mạng xác nhận **0 kết nối WAN ra ngoài Internet** và 0 CDN ngoài.
  - Đo tải 45 học sinh ảo đồng thời qua `tools/load_test.py`: 3 lượt chạy đều đạt 100% nộp bài (45/45), 0 mất ACK, p95 thời gian lưu đáp án đạt 727.9 ms (< 1s), tiêu thụ RAM máy chủ 5.21 MB.
  - Bổ sung `test_p7_resilience_and_recovery.py`: vượt qua kiểm thử sập máy chủ khởi động lại qua WAL, xử lý an toàn khi hết đĩa sao lưu (`HTTP 507`), và khôi phục CSDL + assets sang máy tính thứ hai.
  - Biên soạn `CHANGELOG.md`, `LAN_AP_GUIDE.md`, `TEACHER_QUICKSTART.md`, `STUDENT_QUICKSTART.md`, `RELEASE_CHECKLIST.md` và `docs/phase-reports/PHASE_P7_REPORT.md`.
