# Known Issues / Assumptions

## Giới hạn kỹ thuật & Ràng buộc hiện tại (Cập nhật sau P6)

- Chưa có dữ liệu chạy thực nghiệm ngoài lớp học trên nhiều điện thoại vật lý (`EG-008`, `EG-407`, `EG-711` giữ trạng thái `REVIEW`) và chưa quét thử ảnh chụp camera điện thoại ngoài đời thực với phiếu OMR in giấy (mới kiểm thử trên phiếu sinh trực tiếp kết hợp biến dạng nghiêng -6°/+5.5°, giảm sáng, tô đúp, nét nhạt và cắt mất góc).
- `Ubuntu-R.ttf` / `Ubuntu-B.ttf` gặp lỗi ReportLab ToUnicode `\x00` với một số chữ tiếng Việt ghép dấu; đã đổi `_ensure_pdf_fonts()` sang ưu tiên `DejaVuSans.ttf` giải quyết triệt để lỗi tìm/chọn text tiếng Việt trong mọi PDF xuất ra.
- Không nhúng sẵn `tesseract`/`pdftoppm` trong bản Portable (`v0.1.0-beta.1`) để giữ dung lượng nhỏ gọn, cấp phép sạch BSD/MIT/Apache và tránh nhận diện sai công thức; PDF scan toàn ảnh hiển thị cảnh báo `PDF_LOW_TEXT_DENSITY_OCR_NEEDED` và trích ảnh trang gốc cho giáo viên đối chiếu.
- Windows Hotspot có thể không chạy khi không có Internet hoặc không hỗ trợ số clients mong muốn; router/AP offline đề nghị.
- Browser API không nhận MAC/IMEI; device binding bypass được nếu đổi browser/xóa dữ liệu; anti-cheat là răn đe/cảnh báo.
- HTTP LAN không mã hóa; không thể khẳng định an toàn khi dùng Wi-Fi công cộng không tin cậy.
- Quy định thi chính thức phụ thuộc chính sách cơ sở giáo dục và pháp luật đang có hiệu lực khi deploy.

## Issue log template

```text
ID / severity / introduced:
Symptoms:
Reproduction:
Expected vs actual:
Logs/screenshots:
Root cause (or unconfirmed):
Workaround:
Fix task and test:
```
