# Active Task

- **Phase hiện tại:** P7 — Đóng gói Windows Portable, Kiểm thử tải & Phục hồi, Tài liệu & Phát hành Beta (`EG-701`..`EG-712`)
- **Task kế tiếp:** Cài đặt `pyinstaller`, cập nhật `desktop/launcher.py` (xử lý `sys._MEIPASS`, thư mục `ExamGuardData` di động cạnh EXE, `--version`), viết `desktop/examguard.spec` + `tools/build_portable.ps1`, kiểm thử lạnh `ExamGuard.exe` trên Windows 11, viết `tools/load_test.py` (45 client ảo), viết `backend/tests/test_p7_resilience_and_recovery.py`, soạn bộ runbook & `CHANGELOG.md` + gói release ZIP kèm SHA-256.
- **Lệnh kiểm chứng chuẩn:** `powershell -ExecutionPolicy Bypass -File tools\verify.ps1`
