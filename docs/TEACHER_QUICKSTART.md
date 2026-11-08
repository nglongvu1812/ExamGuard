# Hướng dẫn sử dụng nhanh cho Giáo viên — ExamGuard (`v0.1.0-beta.1`)

Tài liệu tóm tắt quy trình tổ chức kiểm tra 1 lớp trên Windows Portable **không cần cài đặt và không cần Internet** (`EG-709`).

---

## 1. Khởi chạy lần đầu

1. Giải nén tệp `ExamGuard-v0.1.0-beta.1-win64-portable.zip` vào một thư mục có quyền ghi (ví dụ `D:\ExamGuard\`).
   > Không giải nén vào `C:\Program Files\` để tránh thiếu quyền ghi dữ liệu.
2. Chạy tệp **`ExamGuard.exe`**.
   - Nếu Windows SmartScreen hiện cảnh báo ứng dụng chưa ký số chứng thư thương mại (`beta`), bấm **More info -> Run anyway**.
   - Nếu Windows Firewall hỏi quyền mở mạng nội bộ, tick **Private networks -> Allow access**.
3. Trình duyệt tự mở giao diện quản trị tại `http://127.0.0.1:8000/` (cửa sổ đen nhỏ là máy chủ nền — **không tắt cửa sổ này khi đang coi thi**, chỉ đóng khi đã kết thúc hoặc nhấn `Ctrl+C` để dừng an toàn).
4. Toàn bộ CSDL SQLite, ảnh đề, phiếu OMR, biên nhận và bản sao lưu nằm gọn trong thư mục **`ExamGuardData`** cạnh `ExamGuard.exe`.

---

## 2. Quy trình 5 bước tổ chức một buổi kiểm tra

### Bước 1 — Nhập danh sách lớp (`/classes`)
- Tạo lớp mới (ví dụ `12A1 · 2026-2027`).
- Nhập học sinh thủ công hoặc bấm **Import Excel/CSV** (`dry-run` xem trước, kiểm tra trùng mã/sai định dạng trước khi lưu).
- Có thể **Lưu trữ (Archive)** học sinh chuyển lớp mà vẫn bảo toàn lịch sử điểm cũ.

### Bước 2 — Nhập đề & duyệt ngân hàng câu hỏi (`/questions`)
- Tải lên đề gốc định dạng **`.docx`**, **`.pdf`** hoặc **`.xlsx`** (chọn mẫu Excel tương ứng).
- Kiểm tra màn hình đối chiếu song song **Nội dung thô ↔ Bản hiển thị toán KaTeX/hình ảnh**.
- Câu hỏi nào thiếu đáp án chuẩn hoặc tệp PDF scan ít chữ (`ANSWER_NOT_FOUND`, `MULTIPLE_KEYS_DETECTED`, `PDF_LOW_TEXT_DENSITY_OCR_NEEDED`) hệ thống sẽ giữ ở trạng thái **chờ xác minh** (tuyệt đối không tự đoán). Giáo viên chỉnh tay/chọn đáp án đúng rồi bấm **Duyệt vào ngân hàng**.

### Bước 3 — Tạo kỳ thi & Mở phòng chờ (`/exams/new`)
- Chọn Lớp, chọn các câu đã duyệt, cấu hình thời gian làm bài, chế độ trộn đề/đáp án, và ngưỡng cảnh báo mất kết nối (`heartbeat/suspected/disconnect/lock`).
- Chọn **Mở phòng chờ**:
  - Hiện mã **QR + IP LAN + Mã phòng** phóng lớn cho cả lớp quét vào trình duyệt điện thoại (`/join`).
  - Mỗi học sinh có **Mã tham gia cá nhân** riêng — bấm **Tải/In danh sách mã** nếu cần phát cho lớp.
  - Theo dõi danh sách vào phòng và bấm **Duyệt từng người** hoặc **Duyệt tất cả** sau khi đối chiếu sĩ số thật.
  - Nếu học sinh đổi điện thoại do sập nguồn/lỗi trình duyệt: chọn **Cấp lại quyền thiết bị (Reset device)** kèm lý do (tối thiểu 3 ký tự).

### Bước 4 — Bắt đầu thi & Giám sát (`/exams/new`)
- Bấm **Bắt đầu làm bài** — đồng hồ đếm ngược chạy chuẩn xác phía máy chủ.
- Trong bảng giám sát:
  - Dữ liệu chuyển tab (`APP_HIDDEN`), mất kết nối tạm thời (`SUSPECTED` / `DISCONNECTED`) chỉ là **tín hiệu cần kiểm tra** — **không kết luận gian lận tự động**.
  - Nếu học sinh bị tạm khóa do quá ngưỡng rớt mạng (`LOCKED_PENDING_REVIEW`), mở **Ngăn sự cố** xem lịch sử lưu bài cuối cùng rồi chọn **Mở khóa cho làm tiếp**, **Cộng thêm giờ**, hoặc **Kết thúc bài** kèm lý do.
  - Có thể **Tạm dừng cả phòng** hoặc **Đóng phòng thu bài** bất kỳ lúc nào.

### Bước 5 — Đề giấy dự phòng & Chấm phiếu OMR (`/paper`) — Tùy chọn công bằng
- Với học sinh không có điện thoại hoặc khu vực rớt Wi-Fi:
  1. Bấm **Sinh mã đề giấy** (ví dụ 4 mã `101..104`) — thứ tự tráo xác định ánh xạ ngược về cùng ngân hàng câu/đáp án.
  2. Bấm **Tải PDF Đề in (A4)** và **Tải Phiếu tô OMR (A4)** để in cho học sinh.
  3. Sau khi thu bài giấy, tải ảnh chụp/scan phiếu tô lên màn hình `/paper`. Các ô tô đúp, nét mờ hoặc thiếu góc định vị đều được gắn cờ để giáo viên kiểm tra trực quan rồi xác nhận đưa vào **cùng bảng điểm chung** (hệ thống chặn ghi đè bài thi online của học sinh đã nộp trực tuyến).

---

## 3. Chấm điểm, Sửa đáp án, Công bố & Phúc khảo (`/results`)

1. Sau khi đóng phòng (`CLOSED`), bấm **Chấm điểm tự động**.
2. Kiểm tra phổ điểm và rà soát bài chưa nộp hoàn tất. Nếu phát hiện câu sai đề cần chỉnh đáp án chuẩn, cập nhật đáp án kèm **lý do** — hệ thống tạo **phiên bản chấm mới (`ScoreVersion v2`)** và lưu vết đầy đủ, **không sửa đè dữ liệu nộp gốc**.
3. Chỉ khi bấm **Duyệt kết quả (`REVIEWED`)** rồi **Công bố (`PUBLISHED`)**, học sinh mới được phép xem điểm, đáp án đúng và tải **Biên nhận PDF / Thẻ chia sẻ PNG đã che PII**.
4. Khi học sinh cần đối chiếu, mở **Hồ sơ Phúc khảo** của từng em để kiểm tra mã đề đảo, lịch sử từng lần lưu bài, biến đổi đáp án/điểm và chuỗi chữ ký kiểm toán `AuditEvent`.

---

## 4. Sao lưu & Khôi phục thảm họa (`/settings`)

- Trước và sau mỗi buổi thi quan trọng, bấm **Tạo bản sao lưu đầy đủ (.zip)** — chứa SQLite DB chuẩn + đề gốc + ảnh + biên nhận + đề/scan OMR có kiểm tra toàn vẹn `SHA-256`.
- Khi cần chuyển sang laptop mới: chép tệp `.zip` sang máy mới và chạy chức năng **Kiểm tra thử / Khôi phục** trong Cài đặt.

---

## 5. Xử lý nhanh sự cố hay gặp

- **Cúp điện đột ngột / Tắt nhầm máy chủ:** Chạy lại `ExamGuard.exe` trên **cùng thư mục dữ liệu cũ** (`ExamGuardData`). Tất cả đáp án học sinh đã thấy badge **`Đã lưu`** đều đã nằm an toàn trong SQLite WAL và tự đồng bộ khi học sinh tải lại trang.
- **Ổ đĩa báo đầy (`507` / không ghi được):** Giải phóng dung lượng ổ đĩa trước khi sao lưu tiếp; CSDL thi đang mở không bị hỏng.
- **Phát hành thử nghiệm (`Beta`):** Mọi kết quả sử dụng điểm chính thức cần tuân thủ quy chế kiểm tra hiện hành của nhà trường và Bộ GD&ĐT.
