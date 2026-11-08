# Project Memory — Project Brief (ổn định)

**Tên:** ExamGuard, định hướng đồ án tốt nghiệp ICTU 2027 và sản phẩm thực cho giáo viên THPT Việt Nam.

**Ý tưởng:** Portable Windows app cho giáo viên nhập lớp, chuyển đổi đề Word/PDF/Excel, tổ chức thi trắc nghiệm cho một lớp qua Wi-Fi/LAN nội bộ không Internet, học sinh dùng browser trên điện thoại; giám sát kết nối/rời trang theo best-effort; định danh không cần tài khoản; lưu đáp án/chấm điểm có lịch sử; sau cả phiên kết thúc và giáo viên duyệt mới phát PDF/PNG receipt có đáp án và câu sai. Hỗ trợ thi giấy và OMR về sau.

**Quyết định từ trao đổi với chủ dự án:**

1. Giáo viên cần import danh sách lớp một lần và sửa thêm/xóa về sau.
2. Mỗi bài tạo từ ngân hàng đề/chọn file mới, cài 15/45/60/custom rồi mở phòng chờ.
3. Vẫn thi khi **không có Internet**; máy giáo viên là server local; AP/router là phương án tin cậy hơn hotspot Windows khi nhiều máy.
4. Không tài khoản cloud; xác thực học sinh bằng roster identity, mã cá nhân, teacher approval và one active attempt.
5. Anti-cheat không hứa chặn tuyệt đối: chuyển Wi-Fi gây mất kết nối; offline materials/4G/split-screen/thiết bị thứ hai không chặn được; giáo viên có quyền xử lý.
6. File Word/PDF có ảnh, OMML math, ký hiệu đặc biệt phải giữ nguyên, converter không đoán key.
7. Điểm minh bạch: giữ submission gốc, lịch sử thay đổi và receipt để đối chiếu; hash-chain không chống người sửa mọi file tuyệt đối.
8. Receipt chỉ xem/tải **sau toàn phiên** và được giáo viên công bố; có full review/sai/đúng theo cấu hình.
9. School Mode nhiều phòng bị **loại** khỏi v1 do không khả thi local/điều phối; chỉ Classroom Mode. Trường thi kỳ chính thức có thể dùng paper/OMR hỗ trợ.
10. Mục tiêu là sản phẩm giáo viên dùng được, không chỉ demo; cần field pilot và đảm bảo quyền lợi học sinh.

**Lưu ý:** Một phần công nghệ chỉ là đề xuất và phải kiểm thử. Kiến trúc source of truth ở `ARCHITECTURE.md`, ADR ở `DECISIONS.md`; file này không tự thay thế ADR.
