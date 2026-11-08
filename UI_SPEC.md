# UI/UX Specification — Teacher Desktop + Student Mobile

## 1. Nguyên tắc

- Giáo viên không cần biết API, IP, Python, DB; app giải thích bằng ngôn ngữ đời thường.
- Sử dụng cùng thiết kế với teacher shell (desktop 1280px+) và student responsive phone (360–430px).
- Không thay status bằng màu thuần; mỗi trạng thái có icon, chữ, thời điểm, giải pháp.
- Lưu thao tác chỉ báo `Đang lưu...` → `Đã lưu` **sau server ACK**, không hiển thị giả.
- Không prefetch đáp án/điểm học sinh trước công bố dưới bất kỳ hình thức nào.

## 2. Teacher navigation

**Sidebar:** Tổng quan, Lớp học, Ngân hàng đề, Tạo bài kiểm tra, Lịch sử & Kết quả, Sao lưu/Cài đặt, Trợ giúp LAN.

### T1 — Dashboard/Home

Cards: lớp đã lưu, đề đã duyệt, bài thi gần đây, backup cuối, server LAN status. CTA chính `Tạo bài kiểm tra`. First-run wizard `Import lớp` → `Import đề` → `Tạo phiên`.

### T2 — Classes

Danh sách lớp (năm học, sĩ số). Bảng student (mã, tên, tình trạng). Import Excel/CSV preview với mapping cột, duplicate report, nút xác nhận/hoàn tác bản import vừa thực hiện nếu khả thi. Add/Edit/Archive confirmation; history không bị mất khi archive.

### T3 — Question Bank/Import

Upload drag/drop file; progress; danh sách câu hỏi có badge `OK/Review/Unknown key/Math fallback`. Split pane source page vs parsed cards. Edit content blocks/options/key; preview đúng trên mobile. Save draft; Approve version. Chặn dùng nếu còn fatal errors.

### T4 — Exam Wizard

Step 1 chọn lớp; Step 2 chọn bộ đề đã duyệt; Step 3 thời lượng (15/45/60/custom), random options, policy disconnect; Step 4 preview + summary; button `Mở phòng chờ` có xác nhận. Validation lỗi dễ hiểu. Chỉ show lựa chọn hiện thực đã code.

### T5 — Waiting Room

Large QR/IP/SSID guide, số tham gia `n/N`, roster status: Chưa vào/Chờ duyệt/Đã duyệt/Trùng phiên. `Duyệt từng người`, `Duyệt danh sách` có confirm, `Reset device` reason. `Bắt đầu tất cả` disabled khi chưa xác nhận điều kiện. Không hiển thị đề/key cho student trước start.

### T6 — Live Monitoring

Top stats: thời gian server, tổng số, active, submitted, pending, disconnected, locked, incidents. Main table realtime: STT, mã/ tên, tiến độ câu đã lưu, last heartbeat, page status, attempt status, actions. Incident drawer: timeline, evidence, `Mở lại`, `Gia hạn` (nếu policy), `Kết thúc` và lý do. Không tô nhãn `GIAN LẬN` tự động; dùng `Cần xác minh`.

### T7 — Review & Publish

Sau `CLOSED`, hiển thị bảng đủ student statuses: submitted, expired, unresolved. Scoring run summary; teacher xác nhận key, có cảnh báo các câu thay đổi; box `Duyệt kết quả` rồi `Công bố` với modal rõ irreversible disclosure. Nút receipt/export chỉ bật theo role/state.

### T8 — Results & Audit

Grade table, filter, exports, per student detail: bài gốc, permutation, đáp án nộp, score versions, action timeline, receipt versions. Regrade reason mandatory; không cho edit score bằng cách sửa trực tiếp ô Excel trong app và coi là official result.

### T9 — Settings/Backup

Data folder path, backup create/restore dry-run, server port/interfacing status, AP help, app version/license. Cảnh báo file dữ liệu cá nhân. Xóa dữ liệu có preview exact scope + confirm; không xóa source/history không chủ đích.

## 3. Student screens

**S1 Connect:** hướng dẫn kết nối SSID qua màn teacher, QR/server URL (không tự dò SSID từ browser), báo nếu mất mạng LAN.

**S2 Join:** input mã học sinh/mã phòng/mã mời, tên hiển thị xác nhận; nếu trùng mã -> thông báo không lộ dữ liệu học sinh khác; status chờ duyệt.

**S3 Waiting:** hiển thị đã duyệt, đồng hồ server nếu cần, không chứa đề hay key. Teacher start broadcast triggers fetch exam.

**S4 Exam:** sticky timer/status, question progress, navigation, single-choice options, equations rendered local, image zoom, `Đang lưu/Đã lưu`, submit confirm. Không có nút link ra ngoài. Nếu nghi vấn page hidden, hiển thị cảnh báo sau khi return.

**S5 Incident/Offline:** rõ `Mất kết nối. Những đáp án có dấu đã lưu đã được ghi nhận; câu chưa đồng bộ cần chờ giáo viên xác nhận.` Nút retry không tự reset attempt/time. Lock state hiển thị lý do kỹ thuật và yêu cầu gọi giáo viên.

**S6 Submitted Waiting:** đã nộp, timestamp server, trạng thái chờ **toàn phiên + teacher review**, không score/key.

**S7 Published Result:** score/10, đúng/sai, question review chọn vs key, PDF download, PNG share (ẩn dữ liệu cá nhân nhạy cảm), receipt version and verify code. Nếu superseded, banner `Có kết quả cập nhật`.

## 4. Interaction + test expectations

- Modals confirm destructive/high impact operations: Start, End, Cancel, Publish, Force submit, Unlock, Regrade, Backup restore.
- Keyboard access and focus management; contrast. No audio required. Loading skeleton can be used but must not hide error.
- Mobile: no horizontal scrolling for single-choice except math/table content horizontally scrollable within content area; image preview pinch/zoom in modal.
- All teacher actions show success only after server confirms; double click idempotent.
- Error catalogue: invalid code, expired invite, access denied, server restarting, exam closed, locked, not published, unsupported file, parse ambiguity, DB unavailable, backup missing.

## 5. Visual design suggestion

Clean academic SaaS-like desktop: neutral slate, primary navy/teal, success green, warning amber, danger red. Avoid clone of specific commercial product. Teacher mode dense but readable, student mode distraction-free. Local bundled font supporting Vietnamese and math; consistent icon library offline.
