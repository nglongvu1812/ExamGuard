# Prompt audit độc lập trước release/phase gate

---

Bạn đóng vai red-team reviewer, không phải coder chính. **Không thay đổi code trong lượt audit này** trừ khi tôi yêu cầu. Đọc `AGENTS.md`, `SECURITY_AND_FAIRNESS.md`, `DATA_MODEL.md`, `ARCHITECTURE.md`, mã nguồn liên quan và test.

Tập trung:

- Student token có thể đọc bài/điểm của người khác hay key trước publish không?
- Server có tin vào timer, ID hoặc score client gửi không?
- Race: double join, duplicate submit, answer save sau cutoff, lost ACK, DB busy, restart.
- WebSocket có leak key, broadcast dữ liệu nhạy cảm hoặc thiếu auth không?
- Teacher role/auth, device rebind, pending incident, false cheating verdict.
- Import độc hại: XSS, formula injection, zip bomb, path traversal, XML/MathML unsafe.
- Audit/score version có bị overwrite âm thầm? Hash chain có bị quảng cáo quá mức?
- HTTP local có giới hạn gì, ghi đúng không? Có external calls khi WAN down?

Với mỗi phát hiện: `Severity | File/Function | Reproduction | Impact | Evidence | Fix recommendation | Test to add`. Không phỏng đoán thành công của exploit. Kết luận gate PASS/FAIL/UNVERIFIED với lý do. Sau audit có thể đề xuất backlog task nhưng không tự sửa.
