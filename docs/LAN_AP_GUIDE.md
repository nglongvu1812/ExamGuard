# Hướng dẫn thiết lập Mạng LAN / Wi-Fi Offline (Classroom Mode)

Tài liệu này hướng dẫn giáo viên chuẩn bị mạng nội bộ **không cần Internet** để 1 laptop chạy `ExamGuard.exe` phục vụ đồng thời cả lớp qua trình duyệt điện thoại (`EG-704`).

---

## 1. Kiến trúc mạng khuyến nghị (1 Lớp · 1 Router/AP · 0 Internet)

- **Mô hình chuẩn:** Laptop giáo viên (Ethernet hoặc Wi-Fi băng tần 5GHz) ↔ Router/Access Point Wi-Fi riêng đặt trong phòng thi (tắt WAN/không cắm Internet) ↔ Điện thoại học sinh kết nối cùng SSID Wi-Fi đó.
- **Phạm vi v1:** Chỉ chạy **Classroom Mode** (một phòng thi tại một thời điểm trên một máy chủ). Không nối nhiều phòng thi hoặc đồng bộ qua Internet.

### Cấu hình Router/AP đề nghị trước giờ thi
1. **Tắt AP/Client Isolation (Quan trọng nhất):** Một số bộ phát Wi-Fi chế độ Guest/Khách bật cô lập thiết bị (`AP Isolation`), khiến điện thoại nhìn thấy Wi-Fi nhưng **không kết nối được tới IP laptop giáo viên**. Hãy tắt tính năng này hoặc dùng Wi-Fi mạng nội bộ chính.
2. **Đặt tên Wi-Fi (SSID) & mật khẩu ngắn gọn:** Nên phát riêng băng tần 5GHz (hoặc băng tần kép tùy điện thoại học sinh) trong bán kính lớp học để giảm nhiễu sóng.
3. **Bật DHCP bình thường, tắt Captive Portal / DNS bắt buộc đăng nhập:** Điện thoại hiện nay khi thấy Wi-Fi không có Internet có thể hiện thông báo `"Không có kết nối Internet — Giữ kết nối?"`. Giáo viên nhắc học sinh bấm **"Giữ kết nối / Stay connected"** thay vì tự chuyển về 4G/5G.
4. **Cắm dây Ethernet từ Router vào laptop giáo viên (nếu có cổng):** Giảm nghẽn luồng không dây xuống 50% vì gói tin từ điện thoại tới laptop đi qua dây LAN cố định.

---

## 2. Cảnh báo về Windows Mobile Hotspot

Windows 10/11 tích hợp sẵn **Mobile Hotspot**, tuy nhiên chỉ dùng cho **thử nghiệm nhóm nhỏ (<= 8–10 máy)** và **KHÔNG khuyến nghị cho lớp 40–50 học sinh** vì các giới hạn sau:

- Phần cứng Wi-Fi nhiều laptop thương mại chỉ cho phép tối đa **8 kết nối đồng thời** ở chế độ SoftAP (`Hosted Network`).
- Một số bản Windows từ chối bật Mobile Hotspot khi laptop chưa có Internet/cổng WAN ban đầu.
- Chia sẻ chung card Wi-Fi làm cả thu lẫn phát khiến độ trễ tăng vọt khi cả lớp bấm nộp bài đồng loạt.

> **Khuyến nghị thực tế:** Luôn dùng một Router/Access Point Wi-Fi rời mang theo lớp (cắm điện lưới hoặc sạc dự phòng Type-C, **không cần gắn dây mạng Internet**).

---

## 3. Cho phép Firewall trên Windows (Không cần Admin thường nhật)

- Bản thân `ExamGuard.exe` chạy từ thư mục di động **không cần quyền Administrator** và không ghi vào Windows Registry hay `Program Files`.
- Ở lần đầu tiên khởi chạy lắng nghe cổng LAN (`0.0.0.0:8000`), Windows Defender Firewall sẽ hiện hộp thoại:
  - Chọn tick **Private networks** (hoặc nhập xác nhận Firewall của phòng máy trường nếu dùng Domain/Public profile), nhấn **Allow access**.
- **Lưu ý bảo mật mạng:** Vì phiên bản `v0.1.0-beta.1` giao tiếp qua **HTTP/WS LAN nội bộ** trong mạng Wi-Fi đóng của lớp học (`ADR-012`), giáo viên không sử dụng ExamGuard trên Wi-Fi công cộng mở/không mật khẩu; đặt mật khẩu WPA2/WPA3 riêng cho Router lớp thi và đổi sau khi kết thúc buổi kiểm tra nếu cần.

---

## 4. Xử lý nhanh nếu học sinh không vào được trang `/join`

| Triệu chứng | Nguyên nhân phổ biến & Cách kiểm tra |
| --- | --- |
| Quét QR xong trình duyệt quay mãi rồi báo Timeout | 1) Điện thoại tự nhảy sang **4G/5G** (nhắc tắt dữ liệu di động hoặc chọn *Giữ kết nối Wi-Fi*).<br>2) Laptop đang bật **VPN**, card mạng ảo Docker/VMware — vào tab **Trợ giúp LAN** chọn đúng card **Wi-Fi / Ethernet** đang nối Router.<br>3) Windows Firewall đang chặn ở profile `Public`. |
| Mở IP thấy trắng trang | Không dùng URL cũ đã cache port khác; kiểm tra đúng `http://<IP_LAN>:<PORT>/join` hiện trên màn hình Giáo viên. |
| Mạng chậm / rớt liên tục diện rộng | Quá tải Wi-Fi AP hoặc Hotspot. Giáo viên bấm **Tạm dừng phòng thi (Pause)** kèm lý do; nếu mạng không phục hồi được, chuyển sang **In đề giấy + Phiếu OMR (`/paper`)**. |
