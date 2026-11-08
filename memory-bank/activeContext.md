# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: P3 — Exam Engine, Timer, Answer Integrity (`EG-301`..`EG-310`).
- Objective: Xây dựng cấu hình kỳ thi từ ngân hàng câu hỏi, trộn đề deterministic theo seed giữ nguyên `option_id`, state machine phòng thi + server timer + pause/resume, lưu bài commit-before-ACK idempotent, đồng bộ sau mất kết nối, nộp bài atomic và backup/restore SQLite + assets.

## Last completed work

- 2026-11-08: Hoàn thành Phase P2 (`EG-201`..`EG-209` DONE). 16/16 pytest + 4/4 vitest + lint/typecheck/build PASS. Báo cáo tại `docs/phase-reports/PHASE_P2_REPORT.md`.