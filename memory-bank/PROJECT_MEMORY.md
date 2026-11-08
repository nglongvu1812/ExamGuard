# Project Memory — ExamGuard

## Bối cảnh & Mục tiêu
- **Tên dự án:** ExamGuard — Hệ thống tổ chức thi trắc nghiệm và tự luận ngắn trên mạng LAN/Wi-Fi nội bộ (Offline-First), phát triển cho giáo viên THPT Việt Nam và đồ án tốt nghiệp 2027.
- **Phạm vi v1:** Classroom Mode (1 laptop giáo viên làm local server, 1 phòng thi tại một thời điểm, học sinh truy cập qua trình duyệt điện thoại/tablet/PC trên LAN). Không làm School Mode nhiều phòng hay đồng bộ cloud.
- **Các bất biến kiến trúc:**
  1. Server Authoritative (thời gian, trạng thái phòng, điểm, công bố do server quyết định).
  2. No Silent Data Loss (lưu đáp án có idempotency key, revision, ACK chỉ trả sau transaction COMMIT).
  3. Offline Bundled (100% không phụ thuộc Internet, CDN, remote font/JS).
  4. Fairness & Transparency (không tự kết luận gian lận do mất mạng/chuyển tab; giữ nguyên bài nộp gốc, mọi sửa điểm tạo phiên bản mới có lý do và audit).
  5. Deferred Publication (không rò rỉ đáp án/điểm trước khi phiên thi kết thúc và `PUBLISHED`).
  6. Source-Preserving Converter (giữ nguyên nội dung/ảnh/công thức, không tự đoán đáp án).
