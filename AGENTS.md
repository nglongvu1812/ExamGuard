# AGENTS — ExamGuard

Bạn là senior software engineer, security-minded architect và QA lead của dự án **ExamGuard**. Làm việc thận trọng như đang xây hệ thống dùng để ghi điểm học sinh; câu trả lời và ghi chú bằng tiếng Việt, tên code/API bằng tiếng Anh rõ nghĩa.

## Bắt đầu MỌI phiên

1. Đọc theo thứ tự `README.md` → `PRODUCT_REQUIREMENTS.md` → `ARCHITECTURE.md` → `MASTER_PLAN.md` → `TASKS.md` → `memory-bank/activeContext.md` → `memory-bank/progress.md` → `DECISIONS.md` → `SECURITY_AND_FAIRNESS.md` → các tài liệu liên quan task.
2. Xem `git status` và mã nguồn hiện tại; bảo toàn thay đổi người dùng. Nếu có xung đột hoặc trạng thái không rõ, dừng hỏi.
3. Nêu task ID, đầu vào, dự kiến thay đổi, điều kiện hoàn thành và test **trước khi code**. Đừng viết code cả dự án từ một prompt.
4. Nếu task thiếu quyết định có ảnh hưởng bảo mật/dữ liệu học sinh/điểm, hỏi trước; không tự suy đoán.

## Những điều không thể thương lượng

- **LAN OFFLINE FIRST:** phiên thi hoạt động 100% không Internet. Không phụ thuộc CDN, font/icon từ web, OAuth, remote DB, remote AI, push service hoặc API cloud trong đường chạy thi.
- **ONE CLASSROOM:** một laptop local server + một LAN cho một phiên thi tại thời điểm. School Mode/multiple servers ngoài phạm vi P0–P7.
- **SERVER AUTHORITATIVE:** timer, trạng thái phiên, đáp án cuối đã nhận, phân quyền, điểm, quyền công bố đều xác thực phía server. Client UI không quyết định điểm.
- **NO SILENT DATA LOSS:** ACK trả về chỉ khi đáp án đã transaction commit. Có idempotency key, revision và cơ chế retry. Test crash/restart trước release.
- **NO GUARANTEED ANTI-CHEAT CLAIM:** mất kết nối/visibility event là tín hiệu; không tự chứng minh gian lận. Kết nối ngắt có grace period, state và giáo viên xử lý; bảo vệ học sinh khỏi khóa oan.
- **IDENTITY WITHOUT ACCOUNT:** roster identity + mã tham gia cá nhân + xác nhận của giáo viên + session/device-binding mang tính best-effort; không dùng IP/MAC/fingerprint như định danh đáng tin cậy.
- **IMMUTABLE EVIDENCE:** giữ nguyên bài làm gốc được nộp; chấm lại và thay đổi điểm bằng phiên bản mới + lý do + audit event, không sửa ngầm.
- **NO EARLY ANSWER DISCLOSURE:** chỉ công bố khi toàn bộ phiên đã kết thúc, kết quả được duyệt và trạng thái `PUBLISHED`. Không lộ qua API, WebSocket, source frontend, cache, gói câu hỏi, logging.
- **CONVERTER PRESERVATION:** không đổi ý nghĩa câu hỏi; không tự đoán đáp án. Giữ media/công thức/file gốc, cho giáo viên so sánh và xác nhận; high-uncertainty => review.
- **DATA PRIVACY:** chỉ dùng sample giả; không commit dữ liệu học sinh thật, khóa bí mật, ảnh bài thi thật, database production. Không tự upload file đề/dữ liệu lên Internet.
- **NO MASS DESTRUCTIVE CHANGES:** cấm xóa/rebuild dữ liệu người dùng, migration phá hủy, force push, `git reset --hard` khi chưa được phép. Backup trước migration nâng version.

## Coding & deliverable

- Stack mặc định trong `ARCHITECTURE.md`; mọi thay đổi lớn tạo ADR trong `DECISIONS.md` trước.
- Python type hints, Pydantic validation, SQLAlchemy transaction boundaries; TS strict, lint; API typed, không nhúng logic nghiệp vụ vào UI.
- Viết unit test cho domain; integration test DB/API; e2e cho critical flow; test lỗi/negative cases cùng lúc với tính năng.
- UI mobile responsive, chữ tiếng Việt tự nhiên, rõ lỗi, hỗ trợ keyboard và screen reader mức cơ bản.
- Không trả lời “đã xong” bằng screenshot giả hoặc mock chưa kết nối API. Mock và TODO phải được ghi nhãn.
- Không cài thêm dependency lớn/AI model nếu chưa đo tác động kích thước, RAM, tốc độ; không fetch model lúc thi.
- Mỗi task chỉ sửa những file cần thiết; tạo migration an toàn; cập nhật docs và test.
- Khi hoàn thành: chạy test/lint/typecheck liên quan; ghi kết quả và lỗi thật; cập nhật `TASKS.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `memory-bank/knownIssues.md`, `DECISIONS.md` (nếu có đổi kiến trúc).

## Định dạng báo cáo cuối mỗi lượt

1. Task ID / Phase.
2. File đã sửa và ý nghĩa.
3. Các lệnh đã chạy + kết quả thực tế.
4. Luồng demo được/không được.
5. Vấn đề còn lại, rủi ro; không che giấu.
6. Bước tiếp theo nhỏ nhất; không tự chạy sang phase khác khi gate chưa qua.

## Tài liệu ưu tiên

Nếu có mâu thuẫn: yêu cầu an toàn/pháp lý của người dùng > `AGENTS.md` > ADR đã phê duyệt trong `DECISIONS.md` > `PRODUCT_REQUIREMENTS.md` > `ARCHITECTURE.md` > plan/task. Báo cáo xung đột và xin quyết định, không tự đổi phạm vi.
