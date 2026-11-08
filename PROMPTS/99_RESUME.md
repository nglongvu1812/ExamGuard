# RESUME PROMPT — Khi đổi model/phiên Agent

> Sử dụng sau khi Agent mất context, đổi mô hình hoặc mở lại project. Không cần gửi lại toàn bộ cuộc trò chuyện.

---

Tiếp tục dự án ExamGuard trong workspace hiện tại. **Không bắt đầu lại từ đầu, không xóa/refactor lại code chỉ vì không thấy lịch sử chat.**

1. Đọc `AGENTS.md`, `README.md`, `PRODUCT_REQUIREMENTS.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `MASTER_PLAN.md`, `TASKS.md`, `memory-bank/projectBrief.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/knownIssues.md`, và code/test hiện tại.
2. Chạy `git status` + kiểm tra commit/branch; đọc test results có thật (nếu có). So sánh memory với code; khi mâu thuẫn **code/test thực tế và yêu cầu người dùng** là bằng chứng, nêu khác biệt.
3. Báo ngắn `Đã làm được`, `Chưa làm`, `Rủi ro hiện tại`, `Task tiếp theo`, các quyết định đang chờ.
4. Chỉ tiếp tục task `IN_PROGRESS` hoặc task `TODO` nhỏ nhất có dependency đã xong. Trước code đề xuất plan và test.
5. Không nhảy qua phase, không giả định đã run manual device tests, không đổi kiến trúc khi chưa có ADR/chấp thuận.
6. Sau task cập nhật memory bank và test report thật.

Mục tiêu bất biến: ExamGuard Portable một lớp/một LAN offline, roster identity, converter bảo toàn source, session monitoring best-effort, server authoritative, receipt chỉ sau cả phiên và teacher publish, score/audit có version, School Mode excluded v1.
