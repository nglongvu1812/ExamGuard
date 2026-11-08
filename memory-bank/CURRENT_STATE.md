# Current State

- **Trạng thái tổng thể:** Toàn bộ 8 Phase kỹ thuật (`P0` đến `P7`) đã hoàn thành triển khai mã nguồn, kết nối đồng bộ cơ sở dữ liệu và vượt qua kiểm thử tự động toàn diện.
- **Bản phát hành:** `v0.1.0-beta.1` Windows Portable (`dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip`, 47.55 MB, SHA-256 xác thực).
- **Kết quả kiểm thử gần nhất (`tools/verify.ps1`):** PASS (ruff 0 errors, mypy 0 errors / 41 files checked + desktop/tools, pytest 33/33, eslint 0 errors, tsc 0 errors, vitest 11/11, vite build 2.61s).
- **Kết quả benchmark thực nghiệm tải (45 học sinh ảo):** PASS (3 lượt lặp: 45/45 nộp bài bền vững, 0 mất ACK, p95 thời gian lưu đáp án đạt 727.9 ms, server RSS 5.21 MB).
- **Hạng mục Pilot thực địa (`REVIEW`):** Giữ trạng thái `REVIEW` minh bạch đối với các hạng mục cần thiết bị thực tế bên ngoài (`EG-008` AP router với điện thoại thật, `EG-407` ma trận throttle nền ngoài hiện trường, `EG-701` máy tính Windows 10 x64 cài sạch riêng biệt, `EG-711` khảo sát ý kiến 1–2 giáo viên và ảnh chụp camera phiếu OMR in giấy thật).
