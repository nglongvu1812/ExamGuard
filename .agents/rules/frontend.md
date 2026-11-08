---
trigger: model_decision
description: "Áp dụng khi tạo/sửa React UI giáo viên, màn hình học sinh, mobile responsive, lỗi và màn hình cảnh báo."
---

# UI/UX Rules

- Thiết kế cho giáo viên không rành IT: tối đa 4 bước từ chọn lớp -> import/chọn đề -> cấu hình -> mở phòng.
- Phân biệt bằng màu + chữ + icon, không chỉ màu. Text tiếng Việt, font local bundled, cỡ chữ mobile dễ đọc.
- Trạng thái: offline LAN, chờ duyệt, đang thi, đã nộp, reconnecting, khóa tạm, công bố phải rõ nguyên nhân và hành động.
- Student UI tuyệt đối không leak đáp án/score trước publish, kể cả trong hidden DOM hoặc prefetch.
- Teacher dashboard phải phân biệt `network_lost`, `page_hidden`, `teacher_locked`, `suspicious` và `technical_incident`.
- Bắt lỗi mất mạng, save pending, ACK, hết giờ, quay lại, refresh; thông báo không được hứa đã lưu khi chưa ACK.
- Mọi nút quan trọng phải có xác nhận: bắt đầu, kết thúc, hủy, publish, sửa điểm, mở khóa. Có loading/idempotency.
- Các component dày logic tách hooks/services; typed API, không hardcode IP. Test keyboard/mobile viewport.
