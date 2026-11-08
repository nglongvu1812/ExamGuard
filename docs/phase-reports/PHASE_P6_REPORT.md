# BÁO CÁO PHASE P6 — ĐỀ GIẤY, CHẤM PHIẾU OMR & CONVERTER MỞ RỘNG (PDF / XLSX)

## 5.1. Tổng quan

- **Tên Phase:** Phase P6 — Cầu nối Thi giấy OMR & Bộ chuyển đổi đề PDF/XLSX mở rộng (`Paper Bridge & Extended Converters`).
- **Mục tiêu:** Đảm bảo nguyên tắc công bằng (ADR-009): học sinh không có điện thoại hoặc gặp sự cố LAN vẫn được thi bình thường trên đề giấy đồng bộ với đề trực tuyến (cùng `ExamQuestion` và `option_id` gốc), chấm phiếu tô OMR A4 offline từ ảnh chụp/scan mà không dùng thư viện AGPL, bắt buộc đưa phiếu có tô đúp/nét nhạt/mất dấu góc về hàng đợi giáo viên xác nhận và lưu ảnh gốc bất biến, đồng thời mở rộng trình nhập đề hỗ trợ `.pdf` (nhiều cột, trích ảnh, cảnh báo vector/scan OCR) và `.xlsx` nhiều profile giáo viên kèm benchmark đo thực tế.
- **Danh sách Task:** `EG-601`..`EG-609`.
- **Trạng thái hoàn thành:**
  - `EG-601` (Sinh nhiều mã đề in xác định ánh xạ ngược về `option_id` gốc): **DONE**.
  - `EG-602` (Xuất PDF A4 đề in offline kèm fallback công thức + ảnh cục bộ + bảng đáp án giáo viên): **DONE**.
  - `EG-603` (Xuất phiếu tô OMR A4 chuẩn 4 góc định vị + SBD 4 số + Mã đề 3 số + tối đa 40 câu): **DONE**.
  - `EG-604` (Động cơ chỉnh nghiêng phối cảnh 8 tham số bằng Pillow + NumPy BSD & đánh giá độ tin cậy từng ô): **DONE**.
  - `EG-605` (Lưu ảnh scan OMR gốc bất biến SHA-256, hàng đợi `NEEDS_REVIEW`, đối chiếu song song & bắt buộc lý do >= 3 ký tự khi chỉnh sửa đáp án nhận diện): **DONE**.
  - `EG-606` (Đưa bài thi giấy đã xác nhận vào `Attempt` + `Submission(submission_mode="paper_omr_confirmed")` + đồng bộ tự động vào `GradeRun` / `ScoreVersion` / `Phúc khảo`): **DONE**.
  - `EG-607` (Bộ đọc `.pdf` thuần `pypdf` BSD xử lý đọc 2 cột, trích ảnh raster, phát hiện hình vector >8 primitives và cảnh báo trang ít chữ cần OCR): **DONE**.
  - `EG-608` (Bộ đọc `.xlsx` hỗ trợ `auto`, `vn_standard`, `english_bank`, `positional_abcd`, không tự đoán đáp án thiếu): **DONE**.
  - `EG-609` (Đo benchmark hiệu năng thực tế & báo cáo khả thi OCR cục bộ Windows Portable): **DONE**.

## 5.2. Chức năng đã triển khai

### Backend & Cơ sở dữ liệu
- **Migration `0007_paper_bridge_and_omr.py` & Models ([`models.py`](file:///d:/Project/ExamGuard/backend/app/db/models.py)):**
  - Bổ sung bảng `paper_versions` lưu mã đề in (`version_code`), thứ tự `question_version_id`, bản đồ tráo `option_id` và bảng đáp án đối chiếu (`answer_key_map_json`).
  - Bổ sung bảng `omr_scan_submissions` lưu khóa ngoại tới `exam_id`, `student_id`, `paper_version_id`, `linked_attempt_id`, `linked_submission_id`, `source_image_relpath`, `source_sha256`, `aligned_preview_relpath`, kết quả nhận diện thô vs đã xác nhận, điểm tin cậy chi tiết, danh sách cờ mơ hồ (`ambiguous_questions_json`) và lý do giáo viên xác nhận.
  - Cập nhật `config.py` thêm `Settings.paper_dir` và `Settings.scans_dir`; cập nhật `backup_service.py` sao lưu và khôi phục trọn vẹn `paper/` và `scans/` kèm đếm số bản ghi.
- **Đề giấy & Phông chữ PDF Offline ([`paper_service.py`](file:///d:/Project/ExamGuard/backend/app/services/paper_service.py), [`export_service.py`](file:///d:/Project/ExamGuard/backend/app/services/export_service.py)):**
  - `generate_paper_versions`: sử dụng `SHA-256(seed:exam_id:paper:version_code)` sinh thứ tự câu và đáp án xác định, idempotent khi gọi lặp lại cùng dải mã đề.
  - `_ensure_pdf_fonts`: phát hiện và khắc phục lỗi ToUnicode CMap `\x00` trên một số chữ tiếng Việt (`ủ`, `ệ`, `Ả`) của `Ubuntu-*.ttf` khi subset trong ReportLab bằng cách ưu tiên `DejaVuSans.ttf` (bundled offline, giấy phép mở permissive), bảo đảm 100% PDF xuất ra hiển thị và copy/search chuẩn tiếng Việt lẫn ký hiệu toán (`√`, `≤`, `≥`, `×`).
  - `render_paper_booklet_pdf` & `render_omr_sheet_pdf`: xuất PDF A4 nhiều mã đề kèm hình nhúng từ `assets_dir`, LaTeX fallback đọc được `(1)/(2)` và trang `BẢNG ĐÁP ÁN DÀNH CHO GIÁO VIÊN` ở cuối; xuất phiếu tô OMR PDF + PNG từ một nguồn tọa độ duy nhất ([`omr_layout.py`](file:///d:/Project/ExamGuard/backend/app/services/omr_layout.py)).
- **Pipeline Nhận diện & Xác nhận OMR ([`omr_service.py`](file:///d:/Project/ExamGuard/backend/app/services/omr_service.py)):**
  - Validate ảnh `.png`/`.jpg` qua magic bytes & `Image.verify()`, lưu ảnh gốc nguyên vẹn kèm SHA-256 trước khi biến đổi.
  - Dò 4 dấu góc đen (`CANVAS_FID_CORNERS`) theo 4 vùng góc độc lập bằng connected components trên `numpy`; giải hệ tuyến tính 8x8 tìm biến đổi phối cảnh `PIL.Image.Transform.PERSPECTIVE` đưa về khung chuẩn `1200x1700` kèm ảnh đánh dấu trực quan `aligned_<scan_id>.png`.
  - Đánh giá độ tương phản cục bộ (inner core vs outer ring percentile 75) từng ô SBD/Mã đề/Câu hỏi để gắn cờ `CONFIDENT`, `BLANK`, `FAINT` (`0.13 <= mean < 0.30`), `AMBIGUOUS` (chênh lệch top-1 và top-2 thấp) hoặc `FIDUCIAL_NOT_FOUND` (`overall_confidence = 0.0`).
  - Guard bảo mật `confirm_omr_scan`: từ chối HTTP `409 Conflict` nếu học sinh đã có bài nộp trực tuyến (`online`/`teacher_close_auto`) tránh ghi đè âm thầm; bắt buộc `reason >= 3` ký tự khi giáo viên sửa đáp án máy nhận diện (`400`); dịch ngược `version_code + chữ A..D` về `option_id` gốc để sinh `Submission(submission_mode="paper_omr_confirmed")` và chạy lại `run_grading_for_exam` tự động kèm chuỗi `AuditEvent`.
  - Mở rộng `get_student_phuc_khao_trace` trong [`grading_service.py`](file:///d:/Project/ExamGuard/backend/app/services/grading_service.py) hiển thị đúng hoán vị mã đề giấy trong hồ sơ phúc khảo.
- **Converter PDF & XLSX mở rộng ([`pdf_adapter.py`](file:///d:/Project/ExamGuard/backend/app/converters/pdf_adapter.py), [`xlsx_converter.py`](file:///d:/Project/ExamGuard/backend/app/converters/xlsx_converter.py)):**
  - PDF sử dụng `pypdf==7.0.0` (BSD-3-Clause) kết hợp `visitor_text` tính tọa độ `(x, y)` để tách reading-order 2 cột (cột trái từ trên xuống rồi cột phải), trích xuất ảnh raster (`page.images`) vào kho SHA-256, quét content stream phát hiện vector path (`PDF_VECTOR_OR_COMPLEX_LAYOUT`) và cảnh báo trang ít chữ (`PDF_LOW_TEXT_DENSITY_OCR_NEEDED`) — tuyệt đối không bịa OCR hay làm sai thứ tự 2 cột.
  - Excel hỗ trợ 4 profile (`auto`, `vn_standard`, `english_bank`, `positional_abcd`), chuẩn hóa cột theo từ đồng nghĩa tiếng Việt/Anh, giữ nguyên tắc non-guessing (`ANSWER_NOT_FOUND` nếu ô đáp án trống).

### Frontend & APIs
- **API ([`paper.py`](file:///d:/Project/ExamGuard/backend/app/api/paper.py), [`questions.py`](file:///d:/Project/ExamGuard/backend/app/api/questions.py)):**
  - `POST/GET /api/v1/paper/exams/{exam_id}/versions`, `GET .../booklet.pdf`, `GET .../omr-sheet.pdf`, `POST/GET .../scans`, `GET /api/v1/paper/scans/{scan_id}/image?aligned=true|false`, `POST /api/v1/paper/scans/{scan_id}/confirm`.
  - `POST /api/v1/questions/import` nhận `.docx`, `.pdf`, `.xlsx` + trường `profile`.
- **UI ([`PaperBridgePage.tsx`](file:///d:/Project/ExamGuard/frontend/src/pages/teacher/PaperBridgePage.tsx), [`QuestionBankPage.tsx`](file:///d:/Project/ExamGuard/frontend/src/pages/teacher/QuestionBankPage.tsx), [`TeacherLayout.tsx`](file:///d:/Project/ExamGuard/frontend/src/layouts/TeacherLayout.tsx)):**
  - Màn hình `/paper` quản lý hai bước liền mạch: (1) Sinh mã đề & tải PDF đề in + phiếu OMR A4; (2) Tải ảnh phiếu tô, xem song song ảnh gốc vs ảnh đã căn chỉnh đánh dấu xanh/cam, duyệt hàng cờ bất thường (`Q*_AMBIGUOUS`, `Q*_FAINT`, `FIDUCIAL_NOT_FOUND`, `HEADER_*`), chọn học sinh/mã đề, nhập lý do điều chỉnh và đồng bộ vào bảng điểm chung.
  - Màn hình `/questions` cho chọn định dạng `.docx/.pdf/.xlsx` và dropdown `Cấu hình đọc file Excel`, hiển thị đầy đủ cảnh báo vector/OCR tiếng Việt dễ hiểu.

## 5.3. Danh sách file

- **Tạo mới:**
  - [`backend/alembic/versions/0007_paper_bridge_and_omr.py`](file:///d:/Project/ExamGuard/backend/alembic/versions/0007_paper_bridge_and_omr.py)
  - [`backend/app/services/omr_layout.py`](file:///d:/Project/ExamGuard/backend/app/services/omr_layout.py)
  - [`backend/app/services/paper_service.py`](file:///d:/Project/ExamGuard/backend/app/services/paper_service.py)
  - [`backend/app/services/omr_service.py`](file:///d:/Project/ExamGuard/backend/app/services/omr_service.py)
  - [`backend/app/api/paper.py`](file:///d:/Project/ExamGuard/backend/app/api/paper.py)
  - [`backend/app/converters/pdf_adapter.py`](file:///d:/Project/ExamGuard/backend/app/converters/pdf_adapter.py)
  - [`backend/app/converters/xlsx_converter.py`](file:///d:/Project/ExamGuard/backend/app/converters/xlsx_converter.py)
  - [`backend/tests/test_p6_paper_and_converters.py`](file:///d:/Project/ExamGuard/backend/tests/test_p6_paper_and_converters.py)
  - [`frontend/src/pages/teacher/PaperBridgePage.tsx`](file:///d:/Project/ExamGuard/frontend/src/pages/teacher/PaperBridgePage.tsx)
  - [`docs/phase-reports/PHASE_P6_REPORT.md`](file:///d:/Project/ExamGuard/docs/phase-reports/PHASE_P6_REPORT.md)
- **Chỉnh sửa:**
  - [`backend/pyproject.toml`](file:///d:/Project/ExamGuard/backend/pyproject.toml), [`backend/requirements.lock.txt`](file:///d:/Project/ExamGuard/backend/requirements.lock.txt) (bổ sung `pypdf==7.0.0` BSD, `numpy==2.5.4` BSD, chuẩn hóa UTF-8)
  - [`backend/alembic/env.py`](file:///d:/Project/ExamGuard/backend/alembic/env.py), [`backend/app/core/config.py`](file:///d:/Project/ExamGuard/backend/app/core/config.py), [`backend/app/db/models.py`](file:///d:/Project/ExamGuard/backend/app/db/models.py), [`backend/app/main.py`](file:///d:/Project/ExamGuard/backend/app/main.py)
  - [`backend/app/api/questions.py`](file:///d:/Project/ExamGuard/backend/app/api/questions.py), [`backend/app/converters/ingest.py`](file:///d:/Project/ExamGuard/backend/app/converters/ingest.py), [`backend/app/services/question_service.py`](file:///d:/Project/ExamGuard/backend/app/services/question_service.py)
  - [`backend/app/services/backup_service.py`](file:///d:/Project/ExamGuard/backend/app/services/backup_service.py), [`backend/app/services/export_service.py`](file:///d:/Project/ExamGuard/backend/app/services/export_service.py), [`backend/app/services/grading_service.py`](file:///d:/Project/ExamGuard/backend/app/services/grading_service.py)
  - [`frontend/src/api/client.ts`](file:///d:/Project/ExamGuard/frontend/src/api/client.ts), [`frontend/src/App.tsx`](file:///d:/Project/ExamGuard/frontend/src/App.tsx), [`frontend/src/App.test.tsx`](file:///d:/Project/ExamGuard/frontend/src/App.test.tsx), [`frontend/src/layouts/TeacherLayout.tsx`](file:///d:/Project/ExamGuard/frontend/src/layouts/TeacherLayout.tsx), [`frontend/src/pages/teacher/QuestionBankPage.tsx`](file:///d:/Project/ExamGuard/frontend/src/pages/teacher/QuestionBankPage.tsx)

## 5.4. Kiểm thử & Benchmark thực tế (`EG-609`)

### Kết quả kiểm chứng toàn repo (`tools/verify.ps1`, `task-1117`)
- `ruff check`: **PASS** (`All checks passed!`)
- `mypy --config-file backend/pyproject.toml`: **PASS** (`Success: no issues found in 41 source files`)
- `pytest -v`: **PASS** (`29/29 passed in 9.26s` — gồm toàn bộ 26 test P0–P5 và 3 test chuyên sâu P6: `test_paper_versions_booklet_pdf_and_omr_sheet_pdf`, `test_omr_rectification_ambiguity_detection_and_shared_grade_bridge`, `test_pdf_two_column_vector_low_text_and_xlsx_profiles_benchmark`, kể cả test âm tính `409 Conflict` ghi đè bài thi online và `400` thiếu lý do sửa đáp án OMR).
- `eslint .` + `tsc -b --noEmit`: **PASS** (0 lỗi strict TS)
- `vitest run`: **PASS** (`11/11 passed in 2.40s` — gồm render & tương tác màn hình `/paper` và profile selector `.docx/.pdf/.xlsx` ở `/questions`)
- `vite build`: **PASS** (`built in 2.63s`, 100% assets local).

### Số đo Benchmark thực tế trên máy Windows thử nghiệm
| Nhóm tác vụ P6 | Quy mô fixture | Thời gian đo | Kết quả thực tế |
| --- | --- | --- | --- |
| PDF 2 cột + hình vector + bảng key cuối | 20 câu tiếng Việt UTF-8, 12 path vector | **71.3 ms** | `20/20` câu đúng, phát hiện `two_column_pages: [1]`, gắn cờ `PDF_VECTOR_OR_COMPLEX_LAYOUT` |
| XLSX Import (`vn_standard`) | 50 câu đầy đủ A..D + đáp án | **58.6 ms** | `50/50` câu đúng (giữ `ANSWER_NOT_FOUND` khi ô key trống) |
| Sinh biến thể mã đề giấy (`101..104`) | 4 mã đề × 40 câu tráo xác định | **19.6 ms** | Idempotent 100%, ánh xạ ngược về `option_id` khớp |
| Xuất PDF A4 trọn bộ + Bảng đáp án GV | 4 mã đề × 40 câu (`55,088 bytes`) | **130.7 ms** | Hiển thị chuẩn dấu tiếng Việt (`DejaVuSans.ttf`), trích xuất text không lỗi CMap |
| Xử lý phiếu OMR nghiêng `-6.0°`, tối `0.84x` | 40 câu + SBD 4 số + Mã đề 3 số | **161.8 ms** | **`40/40`** đáp án đúng (`100%`), SBD `0007` đúng, Mã đề `101` đúng, `overall_confidence = 0.99`, `ambiguous_flags = []` |

### Đánh giá khả thi OCR cục bộ Windows Portable (`EG-609`)
- **Kiểm tra môi trường hiện tại:** Lệnh kiểm tra `where.exe tesseract` và `where.exe pdftoppm` trên máy host đều trả về không có sẵn nhị phân ngoài.
- **Phân tích đánh đổi kỹ thuật:**
  - Đóng gói sẵn Tesseract OCR + Poppler (`pdftoppm`) + dữ liệu ngôn ngữ `vie.traineddata` làm phình gói Portable thêm ~60–120 MB dung lượng giải nén, tăng độ phức tạp DLL phụ thuộc trên Windows 10/11 không có quyền admin, và độ chính xác OCR tự động với công thức toán/hình học THPT (phân số, tích phân, đồ thị hàm số) vẫn cần giáo viên kiểm tra thủ công để tránh sai đề âm thầm.
  - **Quyết định kỹ thuật:** Ở bản `v0.1.0 Portable`, giữ lõi xử lý 100% thuần Python giấy phép mở permissive (`pypdf`, `Pillow`, `numpy`, `python-docx`, `openpyxl`) không nhúng AI model hay OCR binary nặng; với PDF scan ít chữ (`total_chars < 35`), trích xuất nguyên ảnh trang vào `assets/` kèm cảnh báo `PDF_LOW_TEXT_DENSITY_OCR_NEEDED` và ưu tiên giữ file `.docx` gốc hoặc hỗ trợ bộ OCR plugin tùy chọn ở phiên bản sau nếu trường trang bị máy cấu hình chuẩn.

## 5.5. Vấn đề và giới hạn

- **Lỗi phát hiện & đã sửa trong P6:**
  1. Phát hiện trong test thực tế `Ubuntu-R.ttf` và `Ubuntu-B.ttf` bị thiếu/sai bảng ToUnicode CMap đối với một số nguyên âm tiếng Việt ghép dấu (`ủ`, `ệ`, `Ả`) khi ReportLab subset TTF (sinh ký tự `\x00` khi đọc lại PDF). Đã chuyển `_ensure_pdf_fonts()` sang ưu tiên `DejaVuSans.ttf` (bundled sẵn), khắc phục triệt để cả biên nhận P5 lẫn đề in/OMR P6.
  2. Khắc phục đồng bộ `ensure_aware(...).isoformat()` ở các DTO `PaperVersion` & `OmrScanSubmission` để timestamp từ SQLite trùng khít timestamp khi vừa tạo trong phiên làm việc.
  3. Khắc phục lỗi strict TypeScript ở `PaperBridgePage.tsx` (`StudentDTO.archived` thay cho `archived_at` không tồn tại, thêm guard `noUncheckedIndexedAccess`).
- **Giới hạn trung thực còn tồn tại:**
  - Độ chính xác OMR `40/40` ở trên được đo trên ảnh sinh từ mẫu OMR kèm biến dạng tổng hợp (xoay nghiêng `-6°/+5.5°`, giảm sáng `0.84x/0.86x`, cắt xén mất góc, tô đúp/nét nhạt); ảnh chụp camera điện thoại ngoài đời thực dưới ánh sáng đèn huỳnh quang gắt, bóng tay che cục bộ hoặc giấy nhàu mạnh có thể có góc định vị nhiễu hơn và cần thử nghiệm thêm trên giấy in thật trong bước Pilot (`EG-711`).

## 5.6. Kết luận

- **Tiêu chí nghiệm thu đã đạt:** Toàn bộ chuỗi `Sinh mã đề -> PDF Đề in + Phiếu OMR offline -> Xử lý ảnh nghiêng & gắn cờ mơ hồ -> Giáo viên đối chiếu & xác nhận -> Chấm điểm/Phúc khảo chung` cùng `PDF 2 cột/Vector/Low-text & XLSX multi-profile` đều đã thực thi thật và đạt 100% kiểm thử tự động.
- **Trạng thái cuối cùng:** **PASS** (`EG-601`..`EG-609`: **DONE**).
- **Bước tiếp theo:** Tự động chuyển ngay sang **Phase P7 — Đóng gói Windows Portable EXE, Load Test 40–50 máy ảo, Recovery/Disk-Full, Tài liệu & Phát hành Beta (`EG-701`..`EG-712`)**.
