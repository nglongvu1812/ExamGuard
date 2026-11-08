# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: P5 — Scoring, Audit, Publication, Receipts (`EG-501`..`EG-510`).
- Objective: Triển khai động cơ chấm điểm thuần túy xác thực từ `Submission` + `AnswerKeyVersion`, chu trình kiểm duyệt và công bố (`CLOSED -> REVIEWED -> PUBLISHED`), chấm lại tạo `GradeRun` + `ScoreVersion` (`supersedes_id`) có lý do & audit, chặn tuyệt đối truy cập đáp án/điểm trước `PUBLISHED`, xác minh chuỗi hash `AuditEvent`, xuất bảng điểm Excel (chống formula injection), xuất biên nhận PDF (font Việt bundled offline) / PNG share card (che thông tin nhạy cảm), phúc khảo & xem kết quả học sinh (`T7`, `T8`, `S7`).

## Last completed work

- 2026-11-08: Hoàn thành Phase P4 (`EG-401`..`EG-406`, `EG-408` DONE; `EG-407` REVIEW). `tools/verify.ps1` PASS (22/22 pytest, 8/8 vitest, ruff, mypy, eslint, tsc, vite build). Báo cáo tại `docs/phase-reports/PHASE_P4_REPORT.md` và `docs/MONITORING_MATRIX.md`.
