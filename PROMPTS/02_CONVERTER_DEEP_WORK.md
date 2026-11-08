# Prompt chuyên sâu — Universal Exam Converter

---

Đóng vai specialist OOXML, PDF layout, mathematical typesetting, OCR và quality assurance. Làm **chỉ task Converter được chỉ định** trong P2/P6. Đọc `CONVERTER_SPEC.md`, `.agents/rules/converter.md`, `DATA_MODEL.md`, fixture hiện có trước.

Nhiệm vụ: `[điền EG-20x hoặc EG-60x]`.

Yêu cầu:

1. Trích xuất rich `ContentNode` theo thứ tự và giữ source anchors; không flatten công thức/ảnh.
2. Phân biệt OMML, ký hiệu Unicode, ảnh embedded, MathType legacy/OLE, PDF vector, multi-column và scan.
3. Nếu không chắc, tạo warning/preview/crop ảnh fallback; không đoán đáp án. Parser không bao giờ tự sửa nội dung đề.
4. Bảo vệ khi import file độc: path traversal, malformed DOCX, zip bomb, XML parser hardening, limit file/asset sizes.
5. Viết fixture golden bằng dữ liệu giả; đo số câu, option, key, media/math mapping và thời gian. Test comparison file gốc/rendered.
6. UI cho giáo viên sửa và approve. Chỉ approved question version được dùng trong exam.

Đầu ra: thay đổi code, fixture, report per-category accuracy, warnings, exact commands, limitations. Cập nhật docs/memory và dừng.
