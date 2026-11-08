# BÁO CÁO PHASE P5 — CHẤM ĐIỂM, KIỂM TOÁN, CÔNG BỐ & BIÊN NHẬN (`Scoring, Audit, Publication & Receipts`)

## 5.1. Tổng quan

- **Tên Phase:** Phase P5 — Chấm điểm thuần túy, Lịch sử điều chỉnh có phiên bản, Cổng công bố, Biên nhận & Phúc khảo (`Scoring, Audit, Publication, Receipts`).
- **Mục tiêu:** Triển khai động cơ chấm điểm thuần túy xác thực từ `Submission` (bài nộp bất biến) và `AnswerKeyVersion`; chu trình kiểm duyệt bắt buộc `CLOSED -> REVIEWED -> PUBLISHED`; hỗ trợ chấm lại có lý do tạo `GradeRun` + `ScoreVersion` (`supersedes_id`) + `ReceiptVersion` cập nhật; chặn rò rỉ điểm/đáp án trước `PUBLISHED`; xuất bảng điểm Excel an toàn trước formula injection (`CWE-1236`), biên nhận PDF (font Việt bundled offline + QR) và thẻ chia sẻ PNG (che PII); giao diện phúc khảo đầy đủ cho giáo viên (`T7`, `T8`) và xem kết quả cho học sinh (`S7`).
- **Danh sách Task:** `EG-501`..`EG-510`.
- **Trạng thái hoàn thành:**
  - `EG-501`, `EG-502`, `EG-503`, `EG-504`, `EG-505`, `EG-506`, `EG-507`, `EG-508`, `EG-509`, `EG-510`: **DONE**.

## 5.2. Chức năng đã triển khai

### Backend & Cơ sở dữ liệu
- **Migration `0006_grading_and_receipts.py` & Models (`backend/app/db/models.py`):**
  - Mở rộng `exams` thêm `reviewed_at`, `published_at`.
  - Mở rộng `answer_key_versions` thêm `version_number` và `reason` (append-only, không ghi đè bản cũ).
  - Bổ sung 3 bảng phiên bản bất biến: `grade_runs` (số lần chấm, thống kê tổng hợp, lý do), `score_versions` (`grade_run_id`, `attempt_id`, `raw_points`, `max_points`, `score_10`, `supersedes_id`, `is_current`), `receipt_versions` (`receipt_code`, `score_version_id`, `sha256`, `pdf_relpath`, `png_relpath`, `qr_payload`, `supersedes_id`, `is_current`).
- **Động cơ chấm điểm & Phúc khảo (`backend/app/services/grading_service.py`):**
  - Hàm thuần túy `score_submission_answers(answer_snapshot, specs) -> ScoringOutcome`: chấm điểm trên hệ số bất biến `option_id`, hoàn toàn không phụ thuộc DB/network/thứ tự hiển thị A/B/C/D khi đảo.
  - `run_grading_for_exam`: chạy trong `EXAM_WRITE_LOCK`, bắt buộc `reason >= 3` ký tự khi sửa key hoặc chấm lại; thêm `AnswerKeyVersion` mới, tạo `GradeRun` + `ScoreVersion` (`is_current=False` ở bản bị thay, `supersedes_id` trỏ về bản cũ), sinh `ReceiptVersion` mới nếu kỳ thi đã `PUBLISHED`, và ghi `AuditEvent` (`UPDATE_ANSWER_KEY`, `RUN_GRADING` / `REGRADE_EXAM` / `REGRADE_AFTER_PUBLISH`) kèm `before_hash` / `after_hash`.
  - Chặn chuyển trạng thái sai thứ tự: `review_exam_results` yêu cầu `CLOSED -> REVIEWED`, `publish_exam_results` yêu cầu `REVIEWED -> PUBLISHED` (trả HTTP `409` nếu chưa `REVIEWED`).
  - `get_student_published_result` & `get_student_receipt_artifact`: ép buộc `student.attempt_id == attempt_id`, khớp `session_id`, và `exam.status == "PUBLISHED"` (HTTP `403` trước khi công bố).
  - `get_student_phuc_khao_trace`: dựng báo cáo đối chiếu toàn diện (thông tin biến thể câu/đáp án, toàn bộ `answer_revisions`, lịch sử `AnswerKeyVersion`, chuỗi `ScoreVersion`, danh sách `ReceiptVersion`, nhật ký tín hiệu giám sát và `AuditEvent` liên quan).
- **Xuất dữ liệu & Biên nhận Offline (`backend/app/services/export_service.py`):**
  - `neutralize_excel_formula`: khử mã độc CSV/Excel formula injection (`=`, `+`, `-`, `@`, `\t`, `\r`, bao gồm cả trường hợp có khoảng trắng đầu dòng).
  - `export_exam_grades_xlsx`: xuất file Excel 2 sheet (`Bảng điểm` + `Thống kê` gồm mean, median, max, min, phổ điểm 4 mức) trùng khớp tuyệt đối với kết quả tính từ CSDL và ghi `AuditEvent(EXPORT_EXAM_XLSX)`.
  - `render_receipt_pdf_bytes` (ReportLab A4 dùng font tiếng Việt offline `Ubuntu-R.ttf`, `Ubuntu-B.ttf`, `DejaVuSans.ttf` + QR định danh) và `render_share_card_png_bytes` (Pillow PNG sử dụng `mask_student_name`, `mask_roster_code` — **tuyệt đối không in họ tên/mã đầy đủ trên thẻ chia sẻ**).
  - Cập nhật `backup_service.py` để sao lưu & khôi phục thư mục `receipts/` và đếm `grade_runs`, `score_versions`, `receipt_versions`.
- **APIs (`backend/app/api/results.py`):**
  - Teacher APIs: `GET /api/v1/results/exams/{exam_id}`, `POST .../grade`, `POST .../review`, `POST .../publish`, `GET .../export.xlsx`, `GET .../students/{attempt_id}/trace`, `GET /api/v1/audit/verify`.
  - Student APIs (khóa chặt đến `PUBLISHED`): `GET /api/v1/attempts/me/result`, `GET /api/v1/attempts/{attempt_id}/result`, `GET /api/v1/attempts/me/receipt.pdf`, `GET /api/v1/attempts/me/share-card.png`.

### Frontend (`T7`, `T8`, `S7`)
- **`ResultsAuditPage.tsx` (`T7` / `T8`):** Chọn kỳ thi, chạy quy trình `Chấm điểm -> Kiểm duyệt (REVIEWED) -> Công bố (PUBLISHED)` có hộp thoại xác nhận hậu quả không đảo ngược; panel chỉnh đáp án gốc & chấm lại bắt buộc nhập lý do; thống kê lớp & bộ lọc học sinh; tải XLSX; ngăn kéo `Hồ sơ phúc khảo`; kiểm tra tính toàn vẹn chuỗi SHA-256 `AuditEvent`.
- **`StudentResultPage.tsx` (`S7`) & `StudentJoinShell.tsx`:** Chỉ hiển thị khi `exam_status === "PUBLISHED"`; hiển thị cảnh báo `Có kết quả cập nhật` khi có biên nhận kế thừa phiên bản trước (`superseded_previous`), điểm hệ 10, mã biên nhận + SHA-256, nút tải PDF/PNG qua header `Authorization: Bearer ...` (không đặt token trên URL query), và bảng đối chiếu từng câu dùng icon + chữ + màu.

## 5.3. Danh sách file

- **Tạo mới:**
  - `backend/alembic/versions/0006_grading_and_receipts.py`
  - `backend/app/assets/fonts/DejaVuSans.ttf`, `Ubuntu-R.ttf`, `Ubuntu-B.ttf`
  - `backend/app/services/grading_service.py`
  - `backend/app/services/export_service.py`
  - `backend/app/api/results.py`
  - `backend/tests/test_p5_results_and_security.py`
  - `frontend/src/pages/teacher/ResultsAuditPage.tsx`
  - `frontend/src/pages/student/StudentResultPage.tsx`
  - `docs/phase-reports/PHASE_P5_REPORT.md`
- **Chỉnh sửa:**
  - `backend/pyproject.toml`, `backend/requirements.lock.txt` (thêm `reportlab`)
  - `backend/alembic/env.py`, `backend/app/core/config.py`, `backend/app/db/models.py`, `backend/app/main.py`
  - `backend/app/services/backup_service.py`, `backend/app/services/question_service.py`
  - `frontend/src/api/client.ts`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`
  - `frontend/src/pages/teacher/WaitingRoomPage.tsx`, `frontend/src/pages/student/StudentJoinShell.tsx`

## 5.4. Kiểm thử

- Chạy `powershell -ExecutionPolicy Bypass -File tools\verify.ps1` (`task-776`):
  - `ruff check`: **PASS** (`All checks passed!`)
  - `mypy --config-file backend/pyproject.toml`: **PASS** (`Success: no issues found in 35 source files`)
  - `pytest -v`: **PASS** (`26/26 passed` — gồm `test_pure_scoring_engine_unit`, `test_results_security_gates_publish_and_receipts`, `test_regrade_after_publish_supersedes_scores_and_receipts_and_audit`, `test_excel_formula_injection_stats_and_phuc_khao_trace`, toàn bộ kiểm thử regression P0–P4 và Alembic `upgrade -> downgrade -> upgrade`)
  - `eslint .` + `tsc -b --noEmit`: **PASS**
  - `vitest run`: **PASS** (`10/10 passed` — gồm T7/T8 & S7 UI tests trong `App.test.tsx`)
  - `vite build`: **PASS** (`dist` built cleanly in 2.59s, không CDN).

## 5.5. Vấn đề và giới hạn

- **Lỗi phát hiện & đã xử lý trong quá trình test P5:**
  - Sửa cấu trúc flush tuần tự SQLAlchemy `Question -> QuestionVersion -> AnswerKeyVersion` trong helper seed test để thỏa ràng buộc `FOREIGN KEY` của SQLite.
  - Khắc phục `idempotency_key` ngắn `< 4` ký tự trong test gây HTTP `422` im lặng trước khi bổ sung assertion `assert r.status_code == 200`.
- **Giới hạn đã biết:** Font TTF `Ubuntu-R`/`Ubuntu-B` + `DejaVuSans` hỗ trợ tốt ký tự tiếng Việt và ký hiệu toán cơ bản trong PDF; công thức toán phức tạp trên biên nhận PDF vẫn khuyến nghị giáo viên đối chiếu bản web KaTeX/PDF đề gốc khi phúc khảo chi tiết.

## 5.6. Kết luận

- **Tiêu chí nghiệm thu đã đạt:** Toàn bộ chuỗi `Scoring -> Regrade Versioning -> Audit Chain -> Strict Publish Gate -> XLSX Safety Export -> PDF/PNG Masked Receipts -> Phúc khảo -> Student Result UI` hoạt động thực, có kiểm thử âm tính chặn truy cập chéo và truy cập sớm.
- **Trạng thái cuối cùng:** **PASS** (`EG-501`..`EG-510`: **DONE**).
- **Bước tiếp theo:** Tự động chuyển sang **Phase P6 — Đề giấy, Chấm OMR & Converter PDF/XLSX (`EG-601`..`EG-609`)**.
