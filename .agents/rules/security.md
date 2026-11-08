---
trigger: model_decision
description: "Áp dụng khi viết API phòng thi, đăng nhập, định danh, thiết bị, WebSocket, phân quyền, chấm điểm, audit, xuất và phát kết quả."
---

# Security, Exam Integrity, Fairness

Đọc `SECURITY_AND_FAIRNESS.md`, `DATA_MODEL.md`, `TEST_STRATEGY.md` trước.

- API role check server-side tại mọi endpoint. Teacher UI và Student UI không phải security boundary.
- Student API không trả đáp án chuẩn, đáp án của người khác, điểm dự kiến hoặc chi tiết log riêng tư trước `PUBLISHED`.
- Token ngắn hạn, phiên ràng buộc assessment/student; mã tham gia dùng một lần nếu có thể, hashing at rest; teacher reset được ghi audit.
- Không log token, mã bí mật, toàn bộ bài làm vào stdout.
- Answer writes yêu cầu `attempt_id`, `question_id`, `revision`, `idempotency_key` và xác nhận commit. Race/concurrent submits được xử lý quyết định một cách xác định.
- Disconnect/visibility chỉ là sự kiện quan sát; không truy cập MAC qua browser; không xây browser fingerprinting xâm phạm riêng tư.
- Kết quả chỉ publish khi session closure + finalization + teacher confirmation. Nếu regrade sau publish, tạo version mới, notify revoke bản cũ.
- Audit hash chain không chứng minh chống giả mạo tuyệt đối khi chủ máy sửa cả DB và hash; diễn giải đúng giới hạn. Nếu yêu cầu chứng cứ độc lập, thiết kế external anchor ký số tùy chọn.
- Chặn CSRF/CORS tuỳ bối cảnh, validate upload (đuôi, MIME, kích thước, zip bomb), path traversal, XSS và mã độc trong doc, file result.
- Nếu truy cập HTTP LAN, ghi rõ giới hạn truyền tin; không tự quảng cáo mã hóa đầu cuối. Chuẩn bị phương án HTTPS local/secure key provisioning như future hardening, không hack bỏ TLS warning.
