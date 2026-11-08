# Completed Tasks

- **Phase P0 (`EG-001`..`EG-007` DONE, `EG-008` REVIEW):** Commit `37f9435`.
- **Phase P1 (`EG-101`..`EG-107` DONE):** Commit `ede37b1`.
- **Phase P2 (`EG-201`..`EG-209` DONE):** Commit `3cf036a`.
- **Phase P3 (`EG-301`..`EG-310` DONE):** Commit `f2e6ffd`.
- **Phase P4 (`EG-401`..`EG-406`, `EG-408` DONE; `EG-407` REVIEW):** Commit `36c4375`.
- **Phase P5 (`EG-501`..`EG-510` DONE):** Commit `f12e340`.
- **Phase P6 (`EG-601`..`EG-609` DONE):** Commit `19dc7e7`.
- **Phase P7 (`EG-702`..`EG-710, EG-712` DONE; `EG-701, EG-711` REVIEW):**
  - Đóng gói Windows Portable onedir `ExamGuard.exe` (17.01 MB) và tệp nén phát hành `ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.55 MB) kèm SHA-256.
  - Khởi chạy lạnh thành công trên Microsoft Windows 11 Pro Build 28000; kiểm toán mạng xác nhận 0 kết nối WAN và 0 CDN ngoài.
  - Đo tải 45 học sinh ảo đồng thời qua `tools/load_test.py`: 3 lượt chạy đều đạt 100% nộp bài (45/45), 0 mất ACK, p95 thời gian lưu đáp án đạt 727.9 ms (< 1s), tiêu thụ RAM máy chủ 5.21 MB.
  - Kiểm thử tự động sập máy chủ khởi động lại qua WAL, xử lý an toàn khi hết đĩa sao lưu (`HTTP 507`), và khôi phục CSDL + assets sang máy tính thứ hai (`33/33` pytest PASS).
  - Biên soạn `CHANGELOG.md`, `LAN_AP_GUIDE.md`, `TEACHER_QUICKSTART.md`, `STUDENT_QUICKSTART.md`, `RELEASE_CHECKLIST.md` và `docs/phase-reports/PHASE_P7_REPORT.md`.
