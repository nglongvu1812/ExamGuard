# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: Toàn bộ Phase P0–P7 đã hoàn thành triển khai và nghiệm thu (`v0.1.0-beta.1`).
- Objective: Duy trì trạng thái ổn định của toàn bộ 33 bài kiểm thử tự động, gói phát hành Portable Windows `ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.55 MB, SHA-256 xác thực), kết quả đo tải dồn dập 45 học sinh ảo (3 lượt lặp, p95=727.9ms, 0 mất ACK), và trọn bộ tài liệu vận hành ngoại tuyến. Sẵn sàng cho giai đoạn thử nghiệm thực địa (`Field Pilot`).

## Last completed work

- 2026-11-08: Hoàn thành Phase P7 (`EG-701`..`EG-712`).
  - Đóng gói PyInstaller onedir `ExamGuard.exe` (17.01 MB), bộ khởi chạy `ExamGuard.bat`, các tệp mẫu sẵn có (`samples/`), và nén bản phát hành portable `dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.66 MB, SHA-256: `82c0803b96feb0cdcd3e5e8aef7419bf207f46139db70bade8f9ab5a7fb1edec`).
  - Khởi chạy lạnh thành công trên Microsoft Windows 11 Pro Build 28000; kiểm toán mạng xác nhận **0 kết nối WAN ra ngoài Internet** và 0 CDN ngoài.
  - Đo tải 45 học sinh ảo đồng thời qua `tools/load_test.py`: 3 lượt chạy đều đạt 100% nộp bài (45/45), 0 mất ACK, p95 thời gian lưu đáp án đạt 727.9 ms (< 1s), tiêu thụ RAM máy chủ 5.21 MB.
  - Bổ sung `test_p7_resilience_and_recovery.py`: vượt qua kiểm thử sập máy chủ khởi động lại qua WAL, xử lý an toàn khi hết đĩa sao lưu (`HTTP 507`), và khôi phục CSDL + assets sang máy tính thứ hai.
  - Biên soạn `CHANGELOG.md`, `LAN_AP_GUIDE.md`, `TEACHER_QUICKSTART.md`, `STUDENT_QUICKSTART.md`, `RELEASE_CHECKLIST.md` và `docs/phase-reports/PHASE_P7_REPORT.md`.
