# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React (Vite + TypeScript + Tailwind CSS), FastAPI (Python 3.11+), SQLite / aiosqlite, offline-bundled assets (no external CDN, no external webfonts).

## Users

1. **Giáo viên / Giám thị (Chủ phòng thi):**
   - Sử dụng laptop cá nhân (Windows/macOS/Linux) làm Local Server trong phòng thi.
   - Nhiệm vụ: Soạn & import đề thi (Word/PDF/Excel/JSON), tạo phòng thi, cấp mã PIN/QR, giám sát trực tiếp tiến độ, xử lý sự cố (mất mạng, đổi máy, duyệt vào lại), thu bài và xuất bảng điểm.
2. **Học sinh / Thí sinh:**
   - Sử dụng thiết bị cá nhân hoặc máy phòng máy (điện thoại thông minh, tablet, laptop, PC) kết nối Wi-Fi/LAN phòng thi.
   - Nhiệm vụ: Quét QR / nhập IP & mã tham gia cá nhân, xác thực thông tin học sinh, làm bài thi, nộp bài và xem biên nhận (receipt) nộp bài an toàn.

## Product Purpose

ExamGuard là hệ thống tổ chức và giám sát thi trắc nghiệm & tự luận ngắn chạy 100% trong mạng cục bộ (LAN offline-first), không phụ thuộc kết nối Internet. Hệ thống mang lại kỳ thi công bằng, minh bạch, chống gian lận thực tế và đảm bảo tuyệt đối không mất dữ liệu làm bài của học sinh ngay cả khi mất mạng Wi-Fi hoặc server khởi động lại.

## Positioning

Khác với các nền tảng thi trực tuyến trên đám mây (Azota, Google Forms, MS Forms, Quizizz, Kahoot) đòi hỏi Internet liên tục và phụ thuộc máy chủ bên ngoài, ExamGuard vận hành độc lập hoàn toàn trong 1 phòng học với 1 laptop giáo viên:
- Không lộ đề thi hay dữ liệu học sinh ra Internet.
- Không lo nghẽn mạng hay rớt Internet trường học.
- Cơ chế đồng bộ có ACK đảm bảo không bao giờ mất dù chỉ 1 câu trả lời.
- Định danh không cần tạo tài khoản rườm rà (Roster-based + personal join code).

## Operating Context

- Môi trường vật lý: Lớp học thông thường, phòng máy trường học, hội trường thi.
- Môi trường mạng: Wi-Fi router cục bộ hoặc mạng LAN có dây, hoàn toàn ngắt kết nối Internet (air-gapped hoặc restricted LAN).
- Thiết bị học sinh: Đa dạng từ smartphone màn hình nhỏ, máy tính bảng đến máy tính để bàn phòng máy trường học.
- Ngôn ngữ chính: Tiếng Việt tự nhiên, chuẩn mực sư phạm, rõ ràng, giảm áp lực tâm lý thi cử.

## Capabilities and Constraints

- **LAN Offline-First:** Hoạt động trơn tru không có Internet. Toàn bộ font chữ, icon, script đều được nhúng sẵn cục bộ (Zero external CDN/font/API dependency).
- **Server Authoritative:** Đồng hồ đếm giờ, trạng thái phiên thi, trạng thái nộp bài và chấm điểm hoàn toàn do máy chủ giáo viên kiểm soát. Client không tự quyết định điểm số hay thời gian còn lại.
- **No Silent Data Loss:** Lưu nháp cục bộ (IndexedDB/LocalStorage) kết hợp cơ chế gửi có Idempotency Key, Revision và chỉ xác nhận đã lưu khi server commit transaction thành công.
- **Fairness & Reconnect Grace Period:** Khi học sinh bị ngắt kết nối tạm thời hoặc lỡ chuyển tab, hệ thống ghi nhận sự kiện minh bạch nhưng không tự ý khóa bài oan. Giáo viên có quyền quyết định và hỗ trợ học sinh tiếp tục thi.
- **No Early Answer Disclosure:** Không bao giờ gửi đáp án đúng về phía client cho tới khi phiên thi kết thúc hoàn toàn và giáo viên duyệt công bố điểm.

## Brand Commitments

- **Tên sản phẩm:** ExamGuard
- **Tone & Voice:** Điềm tĩnh, chuyên nghiệp, đáng tin cậy, sư phạm, minh bạch và tạo cảm giác an tâm cho học sinh khi làm bài.
- **Ngôn ngữ:** Tiếng Việt nhất quán (thuật ngữ phòng thi rõ nghĩa).

## Evidence on Hand

- Toàn bộ hồ sơ yêu cầu chi tiết tại `PRODUCT_REQUIREMENTS.md`, `ARCHITECTURE.md`, `UI_SPEC.md`, `SECURITY_AND_FAIRNESS.md`.
- Kế hoạch triển khai tại `MASTER_PLAN.md` và `TASKS.md`.
- Các quyết định kiến trúc đã phê duyệt tại `DECISIONS.md`.

## Product Principles

1. **Độ tin cậy tối thượng (Reliability First):** Trong thi cử, mất dữ liệu bài làm là thảm họa. Mọi thao tác lưu bài phải có bằng chứng xác thực (ACK transaction-committed).
2. **Offline hoàn toàn (Absolute Local Independence):** Không gọi bất kỳ dịch vụ ngoài nào. Toàn bộ tài nguyên phục vụ bài thi nằm trọn vẹn trong máy chủ cục bộ.
3. **Công bằng & Nhân văn (Fairness without Cruelty):** Giám sát minh bạch mọi tín hiệu, nhưng bảo vệ học sinh khỏi việc bị đánh dấu gian lận oan do lỗi thiết bị hay mạng chập chờn.
4. **Trực quan & Tối ưu tải nhận thức (Cognitive Ease):** Giao diện làm bài sạch sẽ, tập trung tối đa vào nội dung câu hỏi và bảng trả lời; giao diện giáo viên rõ ràng, hiển thị trạng thái cả lớp trong một màn hình tổng quan.

## Accessibility & Inclusion

- Giao diện thân thiện trên mọi kích thước màn hình từ điện thoại 360px đến màn hình máy tính lớn.
- Hỗ trợ phím tắt điều hướng bài thi (Next, Prev, chọn A/B/C/D, Flag xem lại).
- Tương phản màu sắc đạt chuẩn WCAG AA, phông chữ dễ đọc, cỡ chữ linh hoạt cho học sinh có thị lực kém.
- Hỗ trợ công thức toán học/khoa học sắc nét qua MathJax/KaTeX cục bộ.
