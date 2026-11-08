# Next Actions

1. Cài `pyinstaller` vào `backend/.venv`, chuẩn hóa `desktop/launcher.py` hỗ trợ `sys._MEIPASS` và data dir cạnh `ExamGuard.exe`, tạo `desktop/examguard.spec` và `tools/build_portable.ps1` (`EG-701`, `EG-702`).
2. Kiểm thử khởi chạy thực `dist/ExamGuard/ExamGuard.exe` trên Windows 11 x64 không cần quyền Admin, xác minh zero external connections (`EG-703`).
3. Triển khai `tools/load_test.py` đo thực tế 45 client ảo đồng thời (p50/p95, error rate, RSS memory, zero lost ACK) (`EG-705`).
4. Triển khai `backend/tests/test_p7_resilience_and_recovery.py` kiểm thử restart WAL recovery, disk-full/permission error handling an toàn, và cross-PC backup/restore (`EG-706`, `EG-707`).
5. Soạn `docs/LAN_AP_GUIDE.md`, `docs/TEACHER_QUICKSTART.md`, `docs/STUDENT_QUICKSTART.md`, `docs/RELEASE_CHECKLIST.md`, `CHANGELOG.md`, xuất release zip + `.sha256` (`EG-704`, `EG-708`, `EG-709`, `EG-710`, `EG-712`), tạo `docs/phase-reports/PHASE_P7_REPORT.md` và commit hoàn tất P7.
