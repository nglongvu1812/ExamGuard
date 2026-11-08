# Known Issues / Assumptions

## Giới hạn kỹ thuật & Ràng buộc hiện tại (Cập nhật sau P5)

- Chưa có dữ liệu chạy thực nghiệm ngoài lớp học trên nhiều điện thoại vật lý (`EG-008`, `EG-407` giữ trạng thái `REVIEW`) và chưa có ảnh chụp camera thực tế để đo OMR ngoài môi trường phòng lab (sẽ thực hiện/đánh dấu trung thực ở P6–P7).
- Font TTF offline `Ubuntu-R`/`Ubuntu-B` + `DejaVuSans` trên biên nhận PDF hỗ trợ tốt tiếng Việt và ký hiệu toán cơ bản; công thức LaTeX phức tạp trên biên nhận PDF khuyến nghị đối chiếu bản web KaTeX hoặc đề gốc.
- Windows Hotspot có thể không chạy khi không có Internet hoặc không hỗ trợ số clients mong muốn; router/AP offline đề nghị.
- Browser API không nhận MAC/IMEI; device binding bypass được nếu đổi browser/xóa dữ liệu; anti-cheat là răn đe/cảnh báo.
- Web app không thể chặn chắc screenshot/4G/second phone; mất Wi-Fi có thể do kỹ thuật.
- Xử lý công thức MathType cũ/PDF vector/OCR có độ khó cao, cần fallback và review.
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
