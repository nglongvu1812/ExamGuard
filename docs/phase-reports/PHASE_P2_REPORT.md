# Báo Cáo Hoàn Thành Phase P2 — Converter v1 Word & Question Bank

## 5.1. Tổng quan
- **Tên Phase:** P2 — Converter v1 Word & Question Bank (`EG-201`..`EG-209`)
- **Mục tiêu:** Xây dựng pipeline chuyển đổi đề thi Word (`.docx` OOXML) an toàn sang cấu trúc `QuestionDraft` giữ nguyên nội dung, hình ảnh nhúng, bảng 2 cột và công thức toán OMML; tuyệt đối không tự đoán đáp án đúng nếu thiếu/mơ hồ; cung cấp giao diện Split-View đối chiếu file gốc và chỉnh sửa thủ công trước khi duyệt thành phiên bản bất biến (`QuestionVersion` + `AnswerKeyVersion`) trong ngân hàng đề.
- **Danh sách Task & Trạng thái:**
  - `EG-201`: Ingest file kiểm tra magic bytes `PK\x03\x04`, chống zip bomb / path traversal, băm SHA-256 lưu nguồn bất biến — **DONE**
  - `EG-202`: Trình đọc DOCX OOXML bảo toàn thứ tự đoạn văn (`<w:p>`) và bảng (`<w:tbl>`), ký tự định dạng style — **DONE**
  - `EG-203`: Trích xuất ảnh inline/floating/VML + relationship, chặn link ảnh ngoài (`EXTERNAL_IMAGE_BLOCKED`), lưu asset theo SHA-256 — **DONE**
  - `EG-204`: Trình chuyển đổi công thức `<m:oMath>` / `<m:oMathPara>` sang LaTeX (`\frac`, `\sqrt`, `sSup/sSub/sSubSup`, `\lim`, `\sum/\int`, ma trận, ngoặc, dấu vector) + giữ nguyên `omml_xml` — **DONE**
  - `EG-205`: Rule engine phân tách câu hỏi (`Câu N`, `Question N`), phương án (một dòng, nhiều dòng, bảng 2 cột), key inline / bảng cuối đề / gạch chân-highlight với provenance — **DONE**
  - `EG-206`: Schema `QuestionDraft`, cảnh báo (`ANSWER_NOT_FOUND`, `MULTIPLE_KEYS_DETECTED`, `INSUFFICIENT_OPTIONS`, `EXTERNAL_IMAGE_BLOCKED`) và confidence trung thực — **DONE**
  - `EG-207`: Giao diện Split-View đối chiếu nguồn thô và bản render KaTeX trên mobile, hỗ trợ sửa nội dung và chọn đáp án đúng — **DONE**
  - `EG-208`: Phê duyệt đơn lẻ và duyệt hàng loạt các câu đủ điều kiện tạo `QuestionVersion` + `AnswerKeyVersion` bất biến kèm audit log — **DONE**
  - `EG-209`: Kiểm thử benchmark nhiều nhóm fixture và kiểm thử bảo mật tài liệu lỗi/zip-bomb/path-traversal — **DONE**

## 5.2. Chức năng đã triển khai
- **Backend:**
  - `app/converters/ingest.py`: Kiểm tra định dạng zip/DOCX (`PK\x03\x04`), tối đa 20MB, <= 2000 entries, <= 100MB giải nén, tỷ lệ nén <= 100x, chặn `..` và đường dẫn tuyệt đối; lưu `SourceDocument` và `Asset` bất biến theo SHA-256.
  - `app/converters/omml.py`: Parser OMML thuần `lxml` an toàn (không dùng XSLT ngoài), giữ nguyên XML gốc, chuyển phân số, căn, chỉ số trên/dưới, giới hạn `lim`, tổng/tích phân `nary`, ma trận `pmatrix`, vector/accents.
  - `app/converters/docx_adapter.py`: Sử dụng `SAFE_XML_PARSER` (`resolve_entities=False`, `no_network=True`), chặn ảnh ngoài (`TargetMode="External"` -> `EXTERNAL_IMAGE_BLOCKED`), giữ VML fallback cho OLE/MathType cũ.
  - `app/converters/segmenter.py`: Rule engine nhiều tầng ưu tiên độ chính xác, tuyệt đối không suy đoán đáp án khi thiếu hoặc có nhiều phương án cùng được đánh dấu.
  - `app/services/question_service.py`: Xác thực câu hỏi nháp (bắt buộc có nội dung, >= 2 phương án, đáp án đúng hợp lệ) trước khi phê duyệt; ghi audit `IMPORT_DOCX_JOB`, `EDIT_QUESTION_DRAFT`, `APPROVE_QUESTION_VERSION`.
- **Database (`alembic/versions/0003_question_bank_and_converter.py`):**
  - Thêm 7 bảng mới: `source_documents`, `assets`, `import_jobs`, `question_drafts`, `questions`, `question_versions`, `answer_key_versions`.
- **API:**
  - `POST /api/v1/questions/import`, `GET /api/v1/questions/import/{job_id}`, `PATCH /api/v1/questions/drafts/{draft_id}`, `POST /api/v1/questions/drafts/{draft_id}/approve`, `POST /api/v1/questions/import/{job_id}/approve-ready`, `GET /api/v1/questions/bank` (yêu cầu `TeacherPrincipal`).
  - `GET /api/v1/assets/{asset_id}` phục vụ ảnh nội bộ với header `X-Content-Type-Options: nosniff` và chặn path traversal.
- **Frontend:**
  - `src/components/RichContentBlocks.tsx`: Render text, công thức KaTeX offline (`katex/dist/katex.min.css` bundle cục bộ, `trust: false` chặn XSS/link độc hại) và ảnh phóng to modal.
  - `src/pages/teacher/QuestionBankPage.tsx`: Màn hình nhập đề `.docx`, Split-View đối chiếu nguồn vs mobile preview, sửa văn bản câu hỏi, chọn đáp án, duyệt đơn/hàng loạt, và tab Ngân hàng câu hỏi đã duyệt.

## 5.3. Danh sách file thay đổi chính
- Tạo mới: `backend/alembic/versions/0003_question_bank_and_converter.py`, `backend/app/converters/{ingest,omml,docx_adapter,segmenter}.py`, `backend/app/services/question_service.py`, `backend/app/api/{questions,assets}.py`, `backend/tests/test_p2_converter.py`, `frontend/src/components/RichContentBlocks.tsx`, `frontend/src/pages/teacher/QuestionBankPage.tsx`.
- Chỉnh sửa: `backend/pyproject.toml`, `backend/requirements.lock.txt`, `backend/app/db/models.py`, `backend/app/main.py`, `frontend/src/{App.tsx,App.test.tsx,api/client.ts}`.

## 5.4. Kiểm thử
- `ruff check`: **PASS** (0 lỗi).
- `mypy`: **PASS** (24 file nguồn backend, 0 lỗi).
- `pytest -v`: **PASS** (16/16 tests — gồm toàn bộ 11 tests P0/P1 + 5 test mới P2: pipeline OMML + bảng 2x2 + ảnh PNG + non-guessing key + sửa tay/approve, câu 2 đáp án gạch chân gắn cờ `ambiguous`, OMML đủ 5 dạng toán tử phức tạp, test bảo mật fake ZIP/path traversal/zip bomb/asset traversal, test chặn ảnh external `EXTERNAL_IMAGE_BLOCKED` + thiếu option + chặn unauthenticated `/questions/bank`).
- `eslint` + `tsc -b --noEmit` + `vitest` (4/4 tests) + `vite build`: **PASS** (đã xác minh toàn bộ font `KaTeX_*.woff2/.woff/.ttf` đóng gói cục bộ trong `frontend/dist/assets/`).
- **Lỗi đã phát hiện và sửa trong P2:** Sửa lỗi ưu tiên regex trong `segmenter.py` khi câu cuối dùng dòng `Đáp án: B` trước đó bị khớp nhầm vào `ANSWER_KEY_HEADER_RE` thay vì `INLINE_CORRECT_RE`.

## 5.5. Vấn đề và giới hạn
- Chuyển đổi PDF nhiều cột/scan và đề MathType OLE không kèm ảnh VML là phạm vi của Phase P6 theo `MASTER_PLAN.md`; ở P2 tập trung hoàn chỉnh chuẩn `.docx` OOXML theo gate.
- Đã kiểm thử bằng fixture tự động tái lập; kiểm thử trên file đề Word sưu tầm thực tế của giáo viên sẽ tiếp tục bổ sung tại Phase pilot.

## 5.6. Kết luận
- **Tiêu chí nghiệm thu đã đạt:** Toàn bộ Gate P2 (text, bảng 2x2, ảnh nhúng, OMML, không tự đoán key khi thiếu/trùng, split-view + approve version bất biến, bảo mật upload độc hại).
- **Trạng thái cuối cùng:** **PASS**
- **Nhiệm vụ tiếp theo:** Tự động chuyển sang **Phase P3 — Exam Engine, Timer, Answer Integrity (`EG-301`..`EG-310`)**.
