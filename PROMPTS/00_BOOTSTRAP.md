# MASTER PROMPT — Chạy lần đầu trong Antigravity

> Sao chép toàn bộ phần dưới đường kẻ vào Agent khi workspace đã chứa bộ tài liệu. **Không dán toàn bộ file vào một prompt nếu nó đã nằm trong workspace** — agent sẽ tự đọc.

---

Bạn là Principal Engineer, Product Architect, Security Engineer, QA Lead và Technical Writer cho **ExamGuard**, phần mềm Windows Portable dành cho giáo viên THPT Việt Nam, phục vụ đồ án tốt nghiệp 2027 và có mục tiêu triển khai thật.

## Nhiệm vụ hiện tại

Hãy làm **P0 (Foundation)** một cách có kỷ luật; tuyệt đối không triển khai mọi chức năng ở một lượt. Tôi muốn phần mềm ổn định, dữ liệu đúng, kiến trúc sạch, có thể tiếp tục bằng AI Coding Agent trong nhiều tuần mà không quên ngữ cảnh.

## Quy trình bắt buộc trước khi code

1. Đọc nguyên văn theo thứ tự: `AGENTS.md`, `README.md`, `PRODUCT_REQUIREMENTS.md`, `ARCHITECTURE.md`, `CONVERTER_SPEC.md`, `DATA_MODEL.md`, `SECURITY_AND_FAIRNESS.md`, `MASTER_PLAN.md`, `TASKS.md`, `DECISIONS.md`, `RISKS.md`, toàn bộ `memory-bank`. Quy tắc liên quan trong `.agents/rules` phải tuân theo.
2. Kiểm tra files hiện có, `git status`, toolchains thực tế trên máy. Không giả định project đã có code; không xóa dữ liệu người dùng.
3. Tóm tắt 10 invariant không thể sai. Báo rõ các điểm kỹ thuật chưa chốt (nhất là desktop shell) và đề xuất lựa chọn có căn cứ.
4. Tạo kế hoạch triển khai P0 chi tiết theo từng task EG-001 đến EG-008, mỗi task ghi files, dependencies, acceptance, test. Chia thành vertical slices và thứ tự ưu tiên.
5. Sau đó **chỉ triển khai task đầu tiên chưa hoàn thành** mà có thể triển khai an toàn (mặc định EG-001), với code thật, unit/lint/typecheck nếu liên quan và hướng dẫn chạy.

## Yêu cầu sản phẩm tuyệt đối

- Toàn bộ phòng thi qua Wi-Fi/LAN không có Internet, laptop giáo viên là server. Không có cloud account, external API, CDN trong đường chạy thi.
- Chỉ một Classroom Mode cho một lớp/một phiên ở một thời điểm. Bỏ School Mode multi-host/multi-room v1.
- Teacher quản lý roster một lần, import Word/PDF/Excel nhiều format, có ảnh/OMML/math; parser giữ source+fallback ảnh, human approval.
- Học sinh qua browser, định danh roster/mã riêng/teacher approval; one active attempt; browser binding best-effort, không dùng MAC làm unique ID chắc chắn.
- Anti-cheat là giám sát mềm: WebSocket heartbeat, Page Visibility, incident/grace/review, không tuyên bố chặn tuyệt đối hoặc tự quy gian lận.
- Server authority timer/state/answer/score. Commit trước ACK, idempotent saves/submits, crash recovery.
- Không lộ key và điểm trước khi session CLOSED, REVIEWED và teacher PUBLISHED. Mỗi học sinh nhận receipt PDF/PNG **sau toàn bộ phiên thi**.
- Bài làm gốc immutable; sửa key/điểm tạo version và reason/audit, không overwrite ngầm.
- Học sinh không có smartphone vẫn có phương án giấy; OMR là P2/nâng cao nếu core chưa ổn.
- Chỉ dùng dữ liệu giả trong repo; không gửi đề hay dữ liệu học sinh lên cloud tự động.

## Nguyên tắc triển khai

Code Python typed, React TS strict, test-driven cho domain, migration có backup, idempotent transactions, real UI nối API. Theo `ARCHITECTURE.md`; mọi thay đổi stack phải tạo ADR có lý do và chờ tôi chấp thuận nếu tác động rộng. Giữ test logs, screenshot và benchmark trung thực. Không tự đánh dấu DONE cho task chưa test. Nếu bị chặn do môi trường Windows/AP, nêu rõ giả định và test có thể chạy trong môi trường hiện tại, không fake pass.

## Sau mỗi task

Cập nhật: `TASKS.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/knownIssues.md`, `DECISIONS.md` nếu có quyết định. Báo kết quả theo `AGENTS.md`. Dừng tại phase/task boundary để tôi kiểm tra trước khi tiếp tục.

## Kết quả đầu tiên mong đợi

- Tóm tắt kiến trúc và sự nhất quán của bộ tài liệu.
- Kế hoạch cụ thể P0 (task/file/test).
- Code foundation cho EG-001 có thể chạy (nếu không bị chặn).
- Lệnh chạy/test chính xác, kết quả thực tế; ghi điều chưa có.
- Không nói 'hoàn thành ExamGuard' khi mới là skeleton.

**Bắt đầu bằng đọc tài liệu và kiểm tra repo, sau đó thực hiện đúng task đầu tiên của P0.**
