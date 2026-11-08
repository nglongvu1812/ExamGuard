# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: P7 — Đóng gói Windows Portable EXE, Load Test, Phục hồi thảm họa & Tài liệu phát hành (`EG-701`..`EG-712`).
- Objective: Đóng gói ứng dụng Windows Portable `onedir` (`desktop/examguard.spec`, `tools/build_portable.ps1`), kiểm chứng khởi chạy lạnh không cần quyền Admin trên Windows 11 (`EG-702`) và zero external network traffic (`EG-703`), đo p50/p95 load benchmark 45 học sinh ảo đồng thời (`EG-705`), kiểm thử sập tiến trình / disk-full / cross-PC backup-restore (`EG-706`, `EG-707`), hoàn thiện tài liệu vận hành (`LAN_AP_GUIDE.md`, `TEACHER_QUICKSTART.md`, `STUDENT_QUICKSTART.md`, `RELEASE_CHECKLIST.md`, `CHANGELOG.md`) và lưu trữ bản phát hành `v0.1.0-beta.1` kèm SHA-256 (`EG-708`, `EG-712`). Ghi nhận trung thực trạng thái `REVIEW` đối với phần cần phần cứng vật lý tách biệt (`EG-701` máy Windows 10 sạch riêng, `EG-711` pilot 1–2 giáo viên thực tế).

## Last completed work

- 2026-11-08: Hoàn thành Phase P6 (`EG-601`..`EG-609` DONE). `tools/verify.ps1` PASS (29/29 pytest, 11/11 vitest, ruff, mypy 41 files, eslint, tsc, vite build 2.63s). Sửa lỗi ToUnicode CMap font PDF cho tiếng Việt bằng `DejaVuSans.ttf`. Báo cáo tại `docs/phase-reports/PHASE_P6_REPORT.md`.
