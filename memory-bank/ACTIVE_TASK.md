# Active Task

- **Task ID:** EG-301 .. EG-310 (Phase P3 — Exam Engine, Timer, Answer Integrity)
- **Mục tiêu:** Triển khai tạo kỳ thi từ câu hỏi đã duyệt, trộn câu hỏi & phương án theo seed xác định, vòng đời `DRAFT -> READY -> WAITING -> RUNNING -> CLOSED`, đồng hồ phía server, màn hình thi mobile + lưu đáp án commit-before-ACK idempotent, khôi phục sau ngắt mạng/restart server và sao lưu/phục hồi SQLite.