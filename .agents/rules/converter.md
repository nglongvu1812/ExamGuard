---
trigger: model_decision
description: "Bắt buộc xem khi xây dựng hoặc sửa pipeline import Word/PDF/Excel, trích xuất media, OMML/MathML/LaTeX, OCR và chuẩn hóa câu hỏi."
---

# Exam Converter Guardrails

Đọc `CONVERTER_SPEC.md`, `TEST_STRATEGY.md`, `DATA_MODEL.md` trước.

1. Xử lý document bằng cây các `ContentNode` (text, equation, image, table, shape, lineBreak), giữ thứ tự và anchor/offset, không flatten sớm.
2. Luôn lưu checksum nguồn, format/parser version, mapping câu hỏi/đáp án tới vùng tài liệu gốc.
3. Tách `correctAnswer` khỏi parser inference: nếu file không khai báo đáp án hoặc định dạng không đủ chắc, trường đó = unknown và bắt buộc giáo viên xác nhận.
4. OMML ưu tiên giữ bản gốc + chuyển thành MathML/LaTeX để render, nếu fail fallback ảnh snapshot; không đổi `sqrt`, `lim`, subscript, superscript.
5. PDF có vector drawings, multi-column, scan: phân tích layout/bounding box; không coi `get_images()` là đầy đủ mọi hình.
6. Bảo vệ ảnh khỏi nén/hỏng, tránh tham chiếu link ngoài. Mọi media được copy vào asset store trong workspace/data riêng.
7. Parse nhiều kiểu A., A), (A), bảng Word, đáp án in đậm/gạch chân; các quy tắc không đủ chắc phải flag, không âm thầm khẳng định.
8. Câu hỏi có confidence thấp, thiếu option, thiếu công thức/media => review. Không xuất đề chính thức khi chưa được duyệt.
9. Không dùng remote LLM mặc định; online AI chỉ chế độ tùy chọn, opt-in, cảnh báo dữ liệu và tuyệt đối không nằm trong exam runtime.
10. Test round-trip source vs rendered preview bằng fixture nhiều format; log sai ở mức element/câu hỏi.
