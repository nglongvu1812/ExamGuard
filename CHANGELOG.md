# Changelog — ExamGuard

## `v0.1.0-beta.1` (2026-11-08)

Bản phát hành thử nghiệm đầu tiên (Beta) đầy đủ chu trình từ P0 đến P7 theo mô hình **Classroom Mode Offline-First LAN**:

### Tính năng chính
- **P0 — Nền tảng Windows Portable & Offline SPA:** FastAPI + SQLite WAL + Alembic migrations an toàn sao lưu trước khi nâng cấp; khám phá card mạng LAN + QR SVG không dùng CDN ngoài; font `Be Vietnam Pro`, `JetBrains Mono` và `KaTeX` nhúng cục bộ 100%.
- **P1 — Quản lý Lớp học & Phòng chờ Định danh không tài khoản:** CRUD lớp/học sinh bảo toàn UUID khi lưu trữ; import Excel/CSV có dry-run xem trước và xử lý trùng; mã mời cá nhân ngẫu nhiên giới hạn TTL & rate-limit; cơ chế giáo viên duyệt vào phòng và cấp lại quyền thiết bị (`rebind`) có audit.
- **P2 — Converter `.docx` bảo toàn nguồn & Ngân hàng đề:** Trích xuất OOXML giữ văn bản, bảng, ảnh inline/floating SHA-256, công thức OMML sang LaTeX/KaTeX; chế độ xem song song (Split-View) gốc vs hiển thị; tuyệt đối không tự đoán đáp án khi thiếu hoặc đánh dấu trùng.
- **P3 — Động cơ Thi trực tuyến đáng tin cậy:** Xáo trộn câu hỏi/phương án xác định bằng seed; đồng hồ máy chủ (`Server Authoritative`); lưu đáp án có `idempotency_key` trả `ACK` sau khi COMMIT SQLite; đồng bộ khôi phục sau ngắt mạng/sập tiến trình; sao lưu toàn bộ và khôi phục dry-run.
- **P4 — Giám sát thời gian thực công bằng:** WebSocket xác thực + heartbeat fallback; phân ngưỡng cấu hình mềm `SUSPECTED -> DISCONNECTED -> LOCKED_PENDING_REVIEW`; ngăn sự cố minh bạch cho giáo viên mở khóa / cộng giờ / kết thúc có lý do; giao diện thông báo kỹ thuật rõ ràng cho học sinh.
- **P5 — Chấm điểm, Công bố muộn & Biên nhận:** Động cơ chấm thuần túy trên `option_id`; quy trình `CLOSED -> REVIEWED -> PUBLISHED`; hỗ trợ sửa đáp án/chấm lại tạo `GradeRun` / `ScoreVersion` / `ReceiptVersion` mới và chuỗi `AuditEvent` SHA-256; xuất Excel chống formula injection (`CWE-1236`), biên nhận PDF offline và thẻ chia sẻ PNG che PII.
- **P6 — Cầu nối Đề giấy OMR & Converter PDF/XLSX:** Sinh nhiều mã đề in ánh xạ ngược về `option_id` gốc; xuất PDF A4 (`DejaVuSans.ttf` chuẩn tiếng Việt) + phiếu OMR chuẩn 4 góc; xử lý chỉnh nghiêng phối cảnh Pillow+NumPy gắn cờ tô đúp/nét nhạt/mất góc đưa về giáo viên xác nhận và đồng bộ vào bảng điểm chung; converter `.pdf` 2 cột/ảnh/vector/cảnh báo OCR và `.xlsx` nhiều profile.
- **P7 — Đóng gói Portable & Bảo toàn dữ liệu:** Gói `PyInstaller onedir` (`ExamGuard.exe`) di động cạnh thư mục `ExamGuardData`; chống hỏng DB khi đầy đĩa sao lưu (`507`); benchmark đồng thời 45 học sinh ảo không mất ACK; trọn bộ tài liệu hướng dẫn Giáo viên / Học sinh / AP LAN & Release Checklist.

### Hạn chế đã ghi nhận (`Beta`)
- Đang chờ thử nghiệm thực địa ngoài lớp học trên nhiều điện thoại vật lý với router AP riêng (`EG-008`, `EG-407`), máy Windows 10 x64 cài sạch độc lập (`EG-701`), và 1–2 giáo viên pilot kèm ảnh chụp camera phiếu OMR in giấy (`EG-711`).
