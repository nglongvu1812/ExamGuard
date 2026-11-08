# Universal Exam Converter — Technical Specification

## 1. Goal và nguyên tắc

Chuyển file đề đa định dạng (`.docx`, `.pdf`, `.xlsx`, `.csv` có schema; `.doc` legacy qua conversion tùy môi trường) thành **QuestionDraft** có thể chỉnh sửa và kiểm chứng, giữ nguyên nghĩa, hình, công thức. Ưu tiên **fidelity** hơn coverage; ảnh crop dự phòng được chấp nhận. Không tạo đáp án đúng từ suy đoán AI.

Định dạng đầu vào có thể có: `Câu 1`, `1)`, `Question`, A. A) (A), đáp án trên một hàng/nhiều hàng, bảng 2 cột, key riêng cuối đề, đáp án gạch chân/bold/màu, công thức Word Equation OMML, MathType legacy, Unicode, ảnh, biểu đồ, PDF vector, scan, hai cột, header/footer.

## 2. Pipeline bắt buộc

1. **Ingest**: kiểm MIME, magic bytes, size, zip bomb, path traversal; copy source immutable, SHA-256; gán `import_job_id`.
2. **Document adapter**: DOCX OOXML (paragraphs, runs, tables, drawings, relationship, equations), PDF layout blocks/vector/crops, XLSX cells/embedded media. Dữ liệu bất thường -> recoverable error.
3. **Content tree**: tạo `[TextNode, EquationNode, ImageNode, TableNode, LineBreakNode, ShapeNode]`; mỗi node có position/source anchor/provenance; inline order được bảo toàn.
4. **Segmentation**: nhận diện header/numbering/câu/option; nhận biết columns, table boundaries, key blocks. Rule-based parser đầu tiên; fallback heuristic/AI chỉ nếu được bật.
5. **Asset extraction**: copy ảnh đúng binary nếu possible; vẽ crop high-DPI cho vector/tổ hợp hoặc ảnh MathType cũ; tránh ảnh trong header giả làm câu.
6. **Normalization**: chuyển thành `QuestionDraft` và `OptionDraft` với `content_blocks` đa phương tiện, mapping source ranges, draft answer key với provenance.
7. **Validation**: required question text/media, >=2 options cho single-choice, đáp án không trùng, ambiguity, math parse/render error, missing image, duplicate numbering.
8. **Human preview**: split-view file gốc/rendered, highlight đoạn map, manual edit, chọn key, confidence/warnings. Câu thiếu bắt buộc phải sửa/confirm.
9. **Approval**: tạo immutable question bank version và snapshot media; draft edits ghi audit; chỉ approved version được đưa vào exam.

## 3. Canonical Intermediate Representation

```json
{
  "question_id": "uuid",
  "version": 1,
  "type": "single_choice",
  "blocks": [
    {"type": "text", "text": "Tính giới hạn:"},
    {"type": "math", "mathml": "<math>...</math>", "latex": "\\lim_{x\\to 2} f(x)", "fallback_asset_id": "sha256:..."},
    {"type": "image", "asset_id": "sha256:...", "alt": "Đồ thị hàm số", "source_anchor": "page=2,bbox=..."}
  ],
  "options": [
    {"option_id": "uuid-A", "blocks": [{"type": "text", "text": "2"}]},
    {"option_id": "uuid-B", "blocks": [{"type": "text", "text": "4"}]}
  ],
  "answer": {"correct_option_ids": [], "status": "unknown", "provenance": null},
  "source": {"file_sha256": "...", "page_or_section": "...", "parser_version": "..."},
  "warnings": ["ANSWER_NOT_FOUND"],
  "confidence": {"segmentation": 0.92, "answer_detection": 0.0, "media_mapping": 0.98},
  "approved_at": null
}
```

Lưu ý: JSON trên là **minh họa schema**, không phải wire schema final. Type validate bằng Pydantic; MathML là dữ liệu chưa tin cậy phải sanitize/render an toàn (không chèn HTML tùy ý).

## 4. Rule engine

- Tầng parser 1: ký hiệu nhận dạng rõ `Câu N`, `Question N`, `A.`/`A)`; đáp án `Đáp án: A`, `KEY: ...`.
- Tầng 2: style paragraph/run (bold, underline, highlight), table structure, line breaks.
- Tầng 3: khoảng cách, cột, bounding boxes và pattern học từ teacher profile được xác nhận.
- Confidence phải hiệu chỉnh bằng dữ liệu benchmark, không tùy tiện gắn 0.99. Nếu chưa calibration, dùng `unknown/needs_review` thay giả độ chính xác.
- Teacher Profile là cấu hình luật *được duyệt*, không tự fine-tune model bằng đề/dữ liệu thật.

## 5. Toán học và media

- DOCX: đọc OMML math object và thứ tự text/math trong paragraph, lưu XML source; có thể chuyển OMML→MathML/LaTeX nhưng phải test `fractions, roots, limits, matrices, accents, superscripts, subscript, special symbols`. Nếu conversion fail, rasterize vùng math và giữ bản gốc.
- `MathType` legacy/OLE có thể không parse được: cho phép crop/snapshot vùng công thức và flag `MATH_FALLBACK_IMAGE`.
- PDF: một số hình học/đồ thị là vector drawing chứ không phải image asset; cần preserve bằng page crop với bbox.
- PDF hai cột: sắp xếp reading order dựa trên vùng/column, không chỉ sort toàn trang theo y.
- Scan OCR: chỉ P2; OCR output cần overlay source crop, không tự tạo key. Equation OCR local có thể nặng; ưu tiên safe image fallback.
- Hình trong đáp án phải đi theo đúng `option_id` khi shuffle. Sau khi đảo, displayed label A/B/C/D có thể thay đổi nhưng scoring dựa trên ID.

## 6. Review UI

Split view: bên trái thumbnail/trang gốc, bên phải rendered question. Reviewer sửa block, thêm thiếu option, kéo ảnh đúng vị trí, thay fallback math, chọn key. Button `Duyệt` bị disable khi có fatal errors, cho phép teacher override warning có lý do. Việc phê duyệt tạo `approved_version` và checksum assets.

## 7. Benchmark và dữ liệu mẫu

Tạo ít nhất các nhóm fixture không có dữ liệu cá nhân:

| Nhóm | Ca cần có |
| --- | --- |
| DOCX text | đơn giản, xuống dòng, A/B/C/D một/nhiều hàng |
| DOCX tables | đáp án trong bảng hai cột, merged cells |
| DOCX equations | phân số, ma trận, căn, tích phân, Unicode; OMML/OLE |
| DOCX images | inline image, anchored floating image, image trong option |
| PDF vector | 2 cột, hình vẽ không phải embedded raster |
| PDF scan | mờ, nghiêng, shadow, ký hiệu đặc biệt |
| Error | thiếu key, 2 key, image corrupted, câu không đủ option |

Mỗi fixture gồm `source`, `expected.json`, approved screenshot (nếu cần), metadata tags. So sánh: segmentation precision/recall, option mapping accuracy, answer key fidelity, image/equation placement, processing time, peak RAM. Một file có lỗi nghiêm trọng không được báo “import thành công hoàn toàn”.

## 8. Phạm vi AI

- V1 không yêu cầu model lớn chạy khi thi. Pipeline parser deterministic + fallback ảnh có thể giải quyết phần lớn trường hợp phổ biến.
- Offline AI là **optional**; chỉ khi máy đủ RAM và có model được cài chủ động, phiên bản locked. Không tự tải model khi offline.
- Online AI (nếu bổ sung sau) phải opt-in riêng, minh bạch upload dữ liệu, không mặc định trên và không được gọi trong `RUNNING`.
- AI không có quyền sửa key hoặc công bố đề nếu chưa human confirm.
