# ExamGuard — Bộ tài liệu điều khiển AI Coding Agent

> Phiên bản kế hoạch: 1.0 — 08/11/2026. Đây là **đặc tả và prompt**, chưa phải mã nguồn sản phẩm.

## Mục tiêu

ExamGuard là phần mềm Windows Portable để một giáo viên tổ chức một phiên kiểm tra trắc nghiệm cho một lớp qua **mạng LAN/Wi-Fi nội bộ không cần Internet**, với ứng dụng web chạy trên điện thoại học sinh; đồng thời hỗ trợ in đề/phiếu và chấm giấy về sau. Laptop giáo viên chạy local server, quản lý lớp, đề, phiên thi, giám sát, chấm điểm và phát biên nhận sau khi **toàn bộ phiên thi kết thúc và được duyệt công bố**.

Ưu tiên: tính đúng đắn và khả năng phục hồi > độ tin cậy chấm điểm > dễ dùng > tốc độ xây dựng > hiệu ứng UI.

## Cách đưa vào Antigravity

1. Giải nén gói này thành thư mục **gốc dự án** (mở chính thư mục `ExamGuard-Agent-Kit` làm workspace, hoặc chép **nội dung bên trong** sang workspace dự án).
2. Giữ nguyên `AGENTS.md`, `.agents/rules`, `memory-bank` và các tài liệu ở gốc. Antigravity sẽ tự nhận `AGENTS.md`; các rule bổ sung có YAML frontmatter.
3. Tạo Git repo sạch; mở `PROMPTS/00_BOOTSTRAP.md`, sao chép phần **PROMPT** vào Agent.
4. Cho agent triển khai **mỗi lần một phase**, bắt đầu `P0`; không yêu cầu nó code toàn bộ dự án trong một lượt.
5. Sau mỗi phase, kiểm tra `TASKS.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, test log và diff trước khi gửi prompt phase tiếp theo.
6. Để tiếp tục sau khi đổi mô hình hoặc cuộc trò chuyện, dùng `PROMPTS/99_RESUME.md`.

## Bản đồ tài liệu

| Tệp | Vai trò |
| --- | --- |
| `AGENTS.md` | Quy tắc bắt buộc, always-on |
| `.agents/rules/*` | Quy tắc chuyên biệt parser, security, frontend |
| `PRODUCT_REQUIREMENTS.md` | Phạm vi, persona, use case, yêu cầu, quy tắc kinh doanh |
| `ARCHITECTURE.md` | Module, luồng dữ liệu, trạng thái, API, deploy |
| `DATA_MODEL.md` | Thực thể, ràng buộc, lưu vết, versioning |
| `MASTER_PLAN.md` | Phase P0–P7, milestone và tiêu chí gate |
| `TASKS.md` | Backlog mã task, thứ tự phụ thuộc |
| `TEST_STRATEGY.md` | Test matrix, fixture, benchmark, acceptance |
| `SECURITY_AND_FAIRNESS.md` | Threat model, giới hạn chống gian lận, xử lý sự cố |
| `CONVERTER_SPEC.md` | Pipeline import đề, công thức, ảnh, xác minh |
| `UI_SPEC.md` | Màn hình và luồng thao tác giáo viên/học sinh |
| `OPERATIONS_RUNBOOK.md` | Vận hành LAN offline, xử lý lỗi và khôi phục |
| `DECISIONS.md` | ADR: quyết định kiến trúc và lý do |
| `RISKS.md` | Rủi ro, ngưỡng dừng, phương án dự phòng |
| `memory-bank/*` | Tóm tắt quyết định, trạng thái, lỗi, việc tiếp theo |
| `PROMPTS/*` | Prompt bootstrap, triển khai phase, review, resume |

## Phạm vi được chốt

**Làm:** Một máy chủ cho một lớp tại một thời điểm; giáo viên quản lý danh sách lớp lâu dài; import đề từ file không đồng nhất; điện thoại truy cập trình duyệt qua LAN; ràng buộc phiên thi với danh tính được giáo viên duyệt; giám sát mềm chuyển tab/mất kết nối; đồng hồ do server quản lý; chấm tự động; nhật ký thay đổi điểm; biên nhận sau công bố; xuất PDF/Excel; thi giấy/OMR ở phase sau.

**Không làm ở bản đầu:** Điều phối nhiều phòng thi, server toàn trường, đồng bộ qua cloud, chặn hệ điều hành điện thoại tuyệt đối, xác thực sinh trắc học, theo dõi MAC như danh tính chắc chắn, tự động kết luận gian lận, tự động sửa/đoán đáp án bằng AI, tự động gửi file vào bộ nhớ điện thoại không cần thao tác người dùng.

## Tiêu chí hoàn thành tối thiểu

- Chạy trên Windows 10/11 x64 bằng thư mục Portable từ ổ đĩa thông thường; không cần Internet lúc thi.
- Một giáo viên đưa được ít nhất 30 học sinh thử nghiệm vào cùng phòng LAN, **mục tiêu kiểm chứng cuối 40–50**, không cam kết nếu chưa benchmark thực tế trên AP đã chọn.
- Lưu đáp án và phục hồi sau ngắt mạng/đóng ứng dụng mà không mất dữ liệu đã ACK.
- Phát hiện mất kết nối và rời trang theo mức độ đáng tin cậy thực tế; khóa theo chính sách đã cấu hình, có quyền xử lý của giáo viên.
- Chấm theo phiên bản đáp án đã duyệt; mọi điều chỉnh có lịch sử và lý do.
- Không lộ đáp án/điểm trước khi session kết thúc và trạng thái `PUBLISHED`.
- Import `DOCX` có ảnh/OMML, không làm hỏng nội dung; file phức tạp phải hiện cảnh báo và cho giáo viên sửa. `PDF/XLSX` được hỗ trợ tăng dần theo milestone.

## Cách đánh giá Agent

Không chấp nhận tuyên bố “xong 100%” nếu thiếu bằng chứng: command test, kết quả, ảnh minh họa UI, fixture dùng để kiểm chứng, thông tin API, chứng minh đường chạy LAN và log phản ứng sự cố. Agent phải ghi rõ **ĐÃ LÀM / CHƯA LÀM / RỦI RO / BƯỚC TIẾP**.

## Lưu ý thực tế

- Windows Mobile Hotspot có giới hạn tùy phần cứng, driver và điều kiện chia sẻ mạng. Khuyến nghị router/AP độc lập không kết nối Internet để thử với 40–50 thiết bị. Laptop và AP cùng LAN, không cần Internet.
- Browser web **không thể** truy cập MAC thật hay khóa hoàn toàn chuyển ứng dụng, screenshot, 4G, thiết bị thứ hai.
- Bản chính thức ở trường cần quy trình và phê duyệt phù hợp; đây không phải chứng nhận pháp lý/bảo mật.

## Cấu trúc mã nguồn dự kiến (Agent tạo dần)

```text
backend/        # FastAPI, service/domain, migrations, test
frontend/       # React/TypeScript teacher + student
desktop/        # Launcher Windows, pywebview hoặc browser shell
tools/          # CLI benchmark/fixture/packaging
samples/        # Đề mẫu giả lập, không chứa dữ liệu thật
docs/           # Tài liệu vận hành phát sinh
```

**Đừng xóa bộ tài liệu này khi tạo code.**
