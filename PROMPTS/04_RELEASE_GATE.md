# Prompt gate / kiểm thử tổng hợp

---

Đây là đợt kiểm thử gate của ExamGuard. Phase: `[P0..P7]`. Đọc `MASTER_PLAN.md`, `TEST_STRATEGY.md`, `TASKS.md`, `SECURITY_AND_FAIRNESS.md` và repo hiện tại.

Hãy:

1. Liệt kê toàn bộ acceptance gate của phase cùng kết quả chứng minh; không lấy ảnh mock làm test.
2. Chạy test/lint/typecheck/DB migrations và E2E có thể chạy, log exact commands và thời gian.
3. Kiểm tra offline behavior, save ACK, role/auth, key publish gate, import fidelity khi liên quan.
4. Nếu cần thiết bị thật (Windows, AP, iPhone/Android), tạo manual test checklist từng bước và đánh dấu NOT RUN; tuyệt đối không tuyên bố pass.
5. Ghi blocker thành task mới, update `knownIssues.md`/`progress.md`; xác định có được chuyển phase không.

Xuất báo cáo theo format trong `TEST_STRATEGY.md` và dừng. Không tự chạy phase tiếp theo.
