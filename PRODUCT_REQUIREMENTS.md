# Product Requirements Document — ExamGuard v1

## 1. Bài toán và người dùng

**Vấn đề:** Giáo viên THPT phải nhập danh sách, định dạng đề khác nhau, tổ chức kiểm tra trắc nghiệm, thu bài/chấm, xử lý khiếu nại. Nhiều phòng học không có Internet ổn định; không phải học sinh nào cũng có smartphone. Đề tài tốt nghiệp 2027 cần sản phẩm chạy thật, đo kiểm được.

**Persona:**

- Giáo viên bộ môn (owner): dùng Windows laptop; biết mở file Word/Excel; không muốn thao tác cấu hình mạng kỹ thuật.
- Học sinh THPT: trình duyệt Android/iOS; một số không có thiết bị/cần điều chỉnh hỗ trợ.
- Người xác minh/phúc khảo (có thể chính giáo viên hay tổ chuyên môn trong tương lai): đối chiếu bài làm gốc, key, lịch sử.

## 2. Phạm vi v1

- Một giáo viên, một máy chủ local, một bài thi đang mở; lớp 40–50 học sinh là mục tiêu **load test**, không tự mặc định được hỗ trợ bởi mọi hotspot.
- Portable Windows x64, không yêu cầu cloud account hoặc Internet khi chạy thi.
- Classroom Mode là sản phẩm chính. **Không làm School Mode** (điều phối nhiều phòng/sở/trường, role admin cấp trường) trong v1.
- Thi giấy được hỗ trợ từng bước: xuất đề và đáp án/phiếu, OMR là phase nâng cao sau khi bài thi online ổn định.

## 3. Chức năng theo mã yêu cầu

| Mã | Yêu cầu | Mức ưu tiên | Acceptance quan sát được |
| --- | --- | --- | --- |
| FR-01 | Lớp: import CSV/XLSX, CRUD, mã học sinh ổn định | P0 | Sửa tên không đổi lịch sử kết quả; phát hiện trùng mã |
| FR-02 | Ngân hàng đề và quản lý phiên bản | P0 | File nguồn, hash, đề chuẩn hóa, lịch sử duyệt tồn tại |
| FR-03 | Import DOCX giữ text/image/OMML/table | P0 | Fixture đề toán, hình vẽ hiển thị đúng sau import |
| FR-04 | Import PDF văn bản và XLSX mẫu biến thể | P1 | Báo cáo vị trí không chắc; giáo viên sửa trước duyệt |
| FR-05 | Scan PDF OCR/AI hỗ trợ đa định dạng | P2 | Thử trên benchmark riêng; không tự sửa key; tùy chọn offline |
| FR-06 | Cấu hình 15/45/60/custom, trộn đề, random seed | P0 | Mapping câu hỏi/option/đáp án bảo toàn |
| FR-07 | Phòng chờ, QR, roster login, mã cá nhân | P0 | Không tạo tài khoản cloud; teacher approval |
| FR-08 | Session/device binding, chống đăng nhập đồng thời | P0 | Hai phiên cùng học sinh bị từ chối/giáo viên xử lý |
| FR-09 | Server timer, start/finish, pause theo quyền | P0 | Reload không reset giờ; clock client lệch không ảnh hưởng |
| FR-10 | WebSocket + heartbeat + presence/dashboard | P0 | Dashboard cập nhật trạng thái, reconnect, tiến độ |
| FR-11 | Page visibility + sự kiện kỹ thuật + rule-based lock | P1 | Ghi nhận; có grace period; không tự kết luận gian lận |
| FR-12 | Autosave/ACK/revision/idempotency | P0 | Crash/retry không làm mất câu trả lời đã ACK |
| FR-13 | Submit/finalize/regrade/versioning | P0 | Không thể sửa bài gốc; score có thể tái tính có audit |
| FR-14 | Publish chỉ sau toàn phiên và duyệt | P0 | API không leak trước publish; mọi thiết bị nhận thông báo |
| FR-15 | Biên nhận cá nhân PDF/PNG và xem câu sai | P1 | Chỉ chủ bài nhận; tải sau publish; mã đối chiếu |
| FR-16 | Xuất Excel kết quả lớp, thống kê câu sai | P1 | Tổng điểm và số câu khớp DB; file mở được offline |
| FR-17 | Xuất PDF nhiều mã đề và phiếu trả lời | P1 | Mapping mã đề đúng; in dễ đọc; duyệt trước in |
| FR-18 | Chấm OMR từ ảnh/scan, human-in-the-loop | P2 | Mờ/tô trùng phải flag; lưu ảnh gốc |
| FR-19 | Backup/restore/migrate dữ liệu | P0 | Khôi phục đủ lớp/đề/bài làm/sự kiện sau crash |
| FR-20 | Đóng gói Portable, thao tác 1-click | P1 | Unzip và launch trên máy Windows sạch theo checklist |

P0 = cần cho phiên thi online tin cậy; P1 = đủ dùng và báo cáo; P2 = nâng cao, không chặn release đầu.

## 4. User journeys

### Giáo viên lần đầu

Mở app → nếu chưa có dữ liệu: import lớp từ Excel → tạo/nhập đề → preview từng câu với ảnh và công thức → xử lý item cảnh báo → xác nhận key → tạo phiên với thời lượng/chính sách → xem hướng dẫn kết nối LAN → mở phòng chờ.

### Giáo viên lần tiếp

Mở app → chọn lớp đã lưu → chọn đề đã duyệt hoặc import mới → cấu hình → mở phòng. Không yêu cầu import lại danh sách hay đăng ký online.

### Học sinh trực tuyến

Kết nối đúng mạng Wi-Fi → quét QR/địa chỉ LAN → nhập mã phòng/mã học sinh + mã một lần → chờ teacher approve → nhận đề cá nhân, làm bài, auto-save từng thay đổi, nhìn trạng thái saved/pending → nộp → chờ cả phiên kết thúc → sau teacher publish xem bài làm và tải receipt.

### Học sinh không có điện thoại

Giáo viên có thể xuất cùng đề ra PDF/mã đề + phiếu giấy, sau đó nhập/chấm OMR (P2). Không chặn quyền kiểm tra của em ấy; kết quả gắn cùng `student_id` và `assessment_id`.

### Giáo viên xử lý sự cố

Kết nối rớt 5s -> cảnh báo mềm; >15s (cấu hình) -> trạng thái tạm khóa; học sinh thử reconnect -> teacher xác minh -> tiếp tục với thời gian do server quyết định hoặc xử lý chuyển sang giấy. Có audit.

### Phúc khảo

Mở history → xem source exam + assignment/permutation, response gốc, ack log, key version, score version → nếu cần sửa đáp án/chấm lại, hệ thống ghi lý do và tạo version mới → xuất hồ sơ/phụ lục.

## 5. Business rules

1. Exam status: `DRAFT -> READY -> WAITING -> RUNNING -> CLOSED -> REVIEWED -> PUBLISHED -> ARCHIVED` (có `CANCELLED` có audit). Invalid transitions từ chối.
2. Giáo viên duyệt đáp án đúng trước `READY`; gói đề sinh cho học sinh **không chứa key**.
3. Thời gian toàn lớp đồng bộ (mặc định). Bắt đầu từ server; teacher quyết định thời điểm start. Pause chỉ qua teacher, lý do ghi log.
4. Mỗi student có tối đa một attempt đang hoạt động cho một exam. Một binding trình duyệt dùng cho tối đa một identity trong cùng phiên theo best-effort. Teacher có quyền reset có audit.
5. Theo dõi MAC chỉ khi hạ tầng mạng đáng tin cung cấp, dùng như tín hiệu hỗ trợ; không dựa vào MAC làm identity hay auto-lock.
6. Khi `RUNNING`, client không được truy xuất key/score. Sau `CLOSED` vẫn chưa được xem key cho tới `PUBLISHED`.
7. `submission` có snapshot trả lời + `submitted_at_server`; sửa điểm không sửa submission. Cần giải quyết attempt còn mất mạng khi đóng phiên bằng trạng thái rõ ràng và giáo viên xác nhận.
8. Quy tắc điểm là hàm thuần `(answerSnapshot, answerKeyVersion, rubricVersion) -> score`; version hóa rubric/key, không ghi đè.
9. Teacher chỉ chỉnh điểm có lý do; regrade ưu tiên cả lớp nếu sửa key chung; không thay điểm riêng âm thầm.
10. Receipt có phiên bản; nếu chấm lại sau publish, bản cũ đánh dấu superseded trong hệ thống; học sinh thấy bản mới khi kết nối lại.
11. Bảo vệ học sinh: mất mạng/thoát trang không tự động = gian lận; hoạt động xử phạt cuối cùng theo giáo viên và quy định lớp.
12. Dữ liệu cá nhân chỉ cục bộ; có xuất và xóa theo phạm vi, backup và khả năng thu hồi sau xóa cần giải thích cho giáo viên.

## 6. Non-functional requirements

- **NFR-01 Offline:** Wi-Fi có Internet bị tắt; mọi tài nguyên CSS/JS/fonts/Math render đều local, không DNS ngoài.
- **NFR-02 Resilience:** Không mất đáp án đã được server ACK dù process crash trong kịch bản kiểm thử; pending hiển thị đúng; restart recovery.
- **NFR-03 Capacity:** mục tiêu 40–50 concurrent clients, 20–60 câu; kiểm thử laptop/AP, p95 latency cho submit/save < 1s dưới mạng ổn định; ghi lại cấu hình và số đo thực, không cam kết trước test.
- **NFR-04 Security:** session expiry, role checks, input sanitization, upload validation, minimized logs, backup integrity.
- **NFR-05 UX:** giáo viên lần đầu có wizard; điện thoại portrait 360px; menu không che câu hỏi; trạng thái lưu rõ.
- **NFR-06 Portability:** Windows 10/11 x64, thư mục Portable, không cần quyền admin cho runtime thông thường ngoại trừ cấu hình firewall/mạng nếu Windows yêu cầu.
- **NFR-07 Observability:** structured local log có rotation và PII redaction; health/status page.
- **NFR-08 Accessibility:** có trợ năng/alternative giấy; không bắt buộc học sinh sở hữu thiết bị.
- **NFR-09 Retention:** cấu hình backup, dọn logs, xuất/xóa dữ liệu; yêu cầu nhà trường quyết định retention production.

## 7. Success metrics đồ án 2027

- Parser benchmark với >=100 file giả lập/được phép dùng, các nhóm định dạng Word thường, bảng, công thức, ảnh, PDF, scan (phân nhóm theo scope). Báo accuracy theo từng nhóm, không một con số chung.
- 40–50 concurrent clients trên AP test thực tế; tài liệu cấu hình, log p95/error rate.
- Zero loss of ACKed answers trong test crash/reconnect; công bố khóa key pass negative tests.
- 1–2 giáo viên thử flow quản lý lớp -> tạo đề -> phòng chờ, ghi số thao tác, lỗi, phản hồi.

## 8. Chính sách áp dụng trường học

Sản phẩm được thiết kế để **đề xuất thử nghiệm**, không tuyên bố tự động đủ điều kiện thi chính thức. Theo quy định Việt Nam có thể yêu cầu hạ tầng/điều kiện phần mềm, thông báo học sinh-phụ huynh, phương án dự phòng và phê duyệt. Khi phát hành, kiểm tra lại văn bản có hiệu lực tại thời điểm đó và quy định trường. Không lưu dữ liệu học sinh thật trong repo.
