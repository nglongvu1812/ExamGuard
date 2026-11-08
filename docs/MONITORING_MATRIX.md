# Bảng Ma Trận Giám Sát Trình Duyệt & Giới Hạn Kỹ Thuật (P4 — EG-407)

> Tài liệu này giải thích rõ những gì trình duyệt web di động có thể/không thể đo qua mạng LAN, giúp giáo viên tránh khóa oan học sinh khi gặp tình huống kỹ thuật bình thường.

## 1. Bảng hành vi theo nền tảng & nguy cơ cảnh báo giả (False Positives)

| Tình huống thực tế | Chrome / Android | Safari / iOS (iPhone/iPad) | Tín hiệu Server nhận được | Rủi ro khóa oan & Khuyến nghị xử lý |
| --- | --- | --- | --- | --- |
| Tin nhắn/cuộc gọi đến hoặc thông báo hệ thống phủ lên màn hình | Đôi khi kích hoạt `visibilitychange (hidden)` | Thường kích hoạt `visibilitychange` và tạm ngưng JS timer nền | `APP_HIDDEN` | **Không tự động kết luận gian lận.** Chỉ ghi số lần rời màn hình; giáo viên quan sát trực tiếp tại lớp. |
| Học sinh khóa màn hình tạm thời (tắt sáng 10 giây) | Ngưng JS `setInterval`, đóng WebSocket nếu vào Doze | Tạm ngưng WebSocket sau vài giây khi khóa màn hình | `HEARTBEAT_SUSPECTED` → `HEARTBEAT_TIMEOUT` | Nếu `lock_after_s = 30s`, máy có thể chuyển `LOCKED_PENDING_REVIEW`. Giáo viên dùng **Mở lại / Gia hạn** nếu học sinh thực sự do khóa máy. |
| Chuyển điểm phát Wi-Fi / đi qua vùng sóng yếu | WebSocket đứt đột ngột, giữ HTTP pending queue trong `localStorage` | Safari cắt kết nối WS cũ và khởi tạo lại chậm hơn 2–5 giây | `NETWORK_LOST` → `RECONNECTED` | Client thử kết nối lại theo exponential backoff + jitter (tối đa 10s). Đáp án có dấu **Đã lưu** vẫn nguyên vẹn. |
| OS thu hồi bộ nhớ tab nền (Low Memory Kill / Refresh) | Tải lại trang giữ `sessionStorage` trong phiên hoặc join lại cùng `browser_key` | Safari thường tải lại tab khi quay lại từ app khác | `PAGE_UNLOADED`, tải lại `/attempts/me/paper` | Học sinh khôi phục lại đúng thứ tự câu/đáp án từ `GET /attempts/{id}/sync`; không mất bài đã ACK. |
| Học sinh mở 2 ứng dụng chia đôi màn hình (Split Screen) | Không báo `APP_HIDDEN` nếu khung trình duyệt vẫn có focus | iPad Slide Over đôi khi vẫn active song song | **Không phát hiện được từ Web browser** | Trình duyệt web **không thể phát hiện chắc chắn split-screen hay thiết bị thứ hai**. Giám thị trực tiếp là biện pháp chính. |

## 2. Trạng thái kiểm chứng hiện tại (`EG-407`)

- **Đã kiểm chứng tự động:** Luồng WebSocket reconnect, `visibilitychange`/`pagehide`/`offline`, ngưỡng `3s/5s/15s/30s`, `LOCKED_PENDING_REVIEW`, teacher unlock/extend/terminate trong `backend/tests/test_p4_monitoring.py` và `frontend/src/App.test.tsx`.
- **Chưa kiểm chứng trong môi trường CI này:** Chạy đồng thời trên phần cứng Android/iOS thực tế qua AP vật lý (giữ trạng thái `REVIEW` cho tới đợt thử nghiệm thiết bị thật ở Phase P7 / Pilot).
