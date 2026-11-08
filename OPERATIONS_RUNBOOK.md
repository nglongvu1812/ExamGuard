# Operations Runbook — Hướng dẫn thử nghiệm LAN offline

## 1. Trước giờ thi (giáo viên)

1. Chạy `ExamGuard.exe` từ ổ cứng laptop/portable folder writable. Kiểm tra backup mới và dung lượng ổ.
2. Kết nối laptop với router/AP Wi-Fi riêng không WAN; phương án dự phòng Hotspot Windows chỉ nếu đã kiểm thử device limits. Không tự ý đổi cấu hình mạng trường.
3. Trên UI xem IP được nhận diện động, port, health và QR. Nếu nhiều interface (VPN/Ethernet/Wi-Fi), chọn interface LAN học sinh nhìn thấy; kiểm tra từ một điện thoại mẫu.
4. Chọn lớp và đề **đã duyệt**. Cấu hình timer, xáo trộn, chính sách grace, danh sách hỗ trợ giấy.
5. Đọc kỹ số học sinh, mã phiên, các thiết bị chờ duyệt; xác nhận học sinh hiện diện. Có bản đề giấy/phương án thay thế khi sự cố.
6. Bắt đầu khi phòng ổn định. Không cần Internet và không bật cloud API khi thi.

## 2. Trong giờ thi

- Quan sát Dashboard nhưng không suy diễn mọi mất heartbeat là gian lận.
- Khi student disconnect: chờ grace, ghi rõ trạng thái lưu, xác minh nguyên nhân; có thể mở lại/cho tiếp tục theo quy tắc thống nhất của lớp.
- Nếu AP chết toàn phòng: teacher pause với lý do, kiểm tra save ACK, xác minh backup/server health; khôi phục hoặc chuyển phương án thi giấy. Không tiếp tục chấm ở trạng thái dữ liệu không xác thực.
- Nếu app crash: khởi động lại cùng data dir, chạy DB integrity check/recover, đồng bộ attempts; không mở phòng mới ghi đè attempts cũ.

## 3. Kết thúc

1. Teacher chuyển `CLOSED` sau khi xử lý các attempt còn pending.
2. Xem GradeRun/answer key. Chọn `REVIEWED` khi đầy đủ, sau đó `PUBLISHED` nếu được phép.
3. Students nhận thông báo, tải kết quả cá nhân sau publish trong LAN; không có Internet vẫn được. Nếu đã rời LAN, teacher hướng dẫn giờ tải lại trong lớp hoặc xuất bản theo chính sách nhà trường.
4. Xuất Excel/PDF để lưu, tạo backup nhất quán (DB + assets + manifest), kiểm tra file backup.
5. Không đưa dữ liệu học sinh lên dịch vụ ngoài nếu chưa có quy trình đồng ý và bảo mật.

## 4. Troubleshooting checklist

| Triệu chứng | Kiểm tra |
| --- | --- |
| Điện thoại kết nối Wi-Fi nhưng không vào server | IP/interface, firewall Windows, AP client isolation, server bind, phone VPN/mobile switching |
| Windows Hotspot không bật khi thiếu Internet | Chuyển router/AP LAN offline; không ép driver/hack settings |
| QR mở nhưng trang trắng | static build bundled, CSP, content MIME, cache/service worker, no CDN |
| Học sinh bị khóa oan | incident timeline, background browser throttling, signal quality; teacher review |
| Trạng thái `Đang lưu` mãi | API response, network, DB busy/disk full; chưa ACK không được claim saved |
| Export PDF lỗi ký hiệu toán | local font/math fallback, source retained; manual review |
| Server khởi động không lên | port already used, data folder permissions, migration error, logs; không xóa DB |

## 5. Data policy khi pilot

- Ưu tiên dữ liệu giả và 3–5 tình nguyện viên. Nếu dùng học sinh thật, cần sự đồng ý, xác nhận nhà trường và chính sách xử lý dữ liệu thích hợp.
- Mọi báo cáo lỗi dùng mã giả hóa/ẩn tên, không dán token/đề thật lên issue công khai.
- Backup ra ổ ngoài có kiểm soát; không để raw DB/phiếu trong folder public shared.

## 6. Scope điều hành

`Classroom Mode` là supported. `School Mode` bị loại khỏi v1. Kỳ thi nhiều phòng/cuối kỳ: hỗ trợ tạo đề giấy/OMR và xuất điểm nếu được nhà trường cho phép; không giả lập điều phối các phòng thi độc lập. Việc lấy điểm chính thức phụ thuộc quy định từng trường và văn bản có hiệu lực.
