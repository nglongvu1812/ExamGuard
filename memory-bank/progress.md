# Progress Log — không được tự bịa trạng thái

## Snapshot 2026-11-08

| Phase | State | Note |
| --- | --- | --- |
| P0 Foundation | PASS (EG-008 REVIEW) | Code + tests + offline build pass; hardware 2-phone AP pending pilot |
| P1 Roster | PASS | EG-101..EG-107 DONE, 11/11 pytest + 4/4 vitest pass |
| P2 Converter | PASS | EG-201..EG-209 DONE, 16/16 pytest + 4/4 vitest pass |
| P3 Exam Engine | PASS | EG-301..EG-310 DONE, 20/20 pytest + 6/6 vitest pass |
| P4 Monitoring | PASS (EG-407 REVIEW) | EG-401..406, 408 DONE; 22/22 pytest + 8/8 vitest pass; physical 3-phone matrix pending pilot |
| P5 Scores/Receipts | PASS | EG-501..EG-510 DONE, 26/26 pytest + 10/10 vitest pass |
| P6 Paper/OMR | PASS | EG-601..EG-609 DONE, 29/29 pytest + 11/11 vitest pass; benchmark measured |
| P7 Release/Pilot | PASS (EG-701, EG-711 REVIEW) | EG-702..EG-710, EG-712 DONE; 33/33 pytest + 11/11 vitest pass; Portable build & load test measured |

2026-11-08 — Hotfix & UX Hardening (Room management & Favicon)
- Fix phòng chờ kẹt trạng thái: loại bỏ danh sách "Phòng thi gần đây", ưu tiên chọn phòng thi đang hoạt động (WAITING/RUNNING), thêm nút "Hủy phòng chờ" và "Xóa phòng thi" (cascade sạch CSDL, endpoint DELETE /api/v1/exams/{exam_id}).
- Lưu trữ và tự động nạp lại mã tham gia học sinh: migration 0008, GET /api/v1/rooms/{exam_id}/invites, UI tự động hiển thị bảng mã cấp cho học sinh ngay khi mở phòng chờ.
- Cấu hình favicon định tuyến tường minh và cache-busting (?v=2).
- Verification: 34/34 pytest, 11/11 vitest, ruff, mypy, eslint, tsc, vite build PASS. Đóng gói lại thành công file portable EXE và release ZIP.

2026-11-08 — P7 (`EG-701`..`EG-712`)
Implemented: PyInstaller onedir spec & `build_portable.ps1`, launcher dynamic bundle paths + UTF-8 console stream, atomic staging backup with `HTTP 507` on disk full, `load_test.py` 45-client concurrent benchmark tool, `test_p7_resilience_and_recovery.py` (zero-CDN audit, crash WAL recovery, cross-PC full restore, permission/ENOSPC safety), runbooks (`LAN_AP_GUIDE.md`, `TEACHER_QUICKSTART.md`, `STUDENT_QUICKSTART.md`), `RELEASE_CHECKLIST.md` (59 Python libs audit, 0 AGPL), and `CHANGELOG.md`.
Verification: `tools/verify.ps1` (33/33 pytest, 11/11 vitest, ruff, mypy 41 files + desktop/tools, eslint, tsc, vite build PASS) + live cold-boot smoke test on Windows 11 (0 WAN sockets) + 45-client load benchmark (3 replicates, p95 save 727.9ms, 0 lost ACK, 45/45 submitted).
Evidence paths: `docs/phase-reports/PHASE_P7_REPORT.md`, `dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip`, `docs/RELEASE_CHECKLIST.md`.
Status: All core engineering phases P0–P7 COMPLETE. Ready for field trials.
