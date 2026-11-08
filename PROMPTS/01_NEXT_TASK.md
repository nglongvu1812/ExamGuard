# Prompt triển khai từng task

> Thay `[EG-NNN]` và `[đầu vào]` rồi gửi cho Agent. Tránh giao một phase 20 task trong một lượt.

---

Tiếp tục dự án ExamGuard. Hãy thực hiện **task [EG-NNN]** trong `TASKS.md` và giữ nguyên scope Classroom LAN offline. Đầu vào/ràng buộc bổ sung: **[đầu vào]**.

Trước khi code:

1. Đọc `AGENTS.md`, `memory-bank/activeContext.md`, `memory-bank/progress.md`, `DECISIONS.md`, docs liên quan task; kiểm tra `git status`, code hiện tại và test đang có.
2. Xác định dependency và các test lỗi quan trọng nhất. Viết 5–10 dòng implementation plan (files + API/data contracts + negative test).
3. Kiểm tra không làm đổi invariant về offline, identity, server authority, immutable score, publish gating, media fidelity.

Trong lúc code: implement hoàn chỉnh một vertical slice, không tạo mock giả hoàn thành, không refactor lan rộng ngoài scope; cập nhật migration/DTO/docs nếu cần.

Sau code:

- Chạy lint/typecheck/unit/integration/E2E liên quan; cho exact commands + results.
- Test một negative case và một restart/failure case khi task liên quan state/storage.
- Cập nhật `TASKS.md`, `activeContext`, `progress`, `knownIssues`, ADR nếu có.
- Báo `DONE / REVIEW / BLOCKED` trung thực, file changed, next task nhỏ nhất.

Không tự chạy task tiếp theo hoặc phase mới nếu chưa qua gate.
