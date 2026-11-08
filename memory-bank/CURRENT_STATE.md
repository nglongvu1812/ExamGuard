# Current State

- **Phase vừa hoàn tất:** P4 (`EG-401`..`EG-406`, `EG-408` DONE; `EG-407` REVIEW — chờ 3 điện thoại thật ở Pilot).
- **Phase đang bắt đầu:** P5 — Scoring, Audit, Publication, Receipts (`EG-501`..`EG-510`).
- **Kết quả kiểm thử gần nhất (`tools/verify.ps1`):** PASS (ruff 0 errors, mypy 0 errors / 37 files checked, pytest 22/22, eslint 0 errors, tsc 0 errors, vitest 8/8, vite build 2.23s).
- **Ràng buộc tiếp tục:** Đọc `SECURITY_AND_FAIRNESS.md` mục 5–7 & `DATA_MODEL.md` trước khi code P5; gói `reportlab` + font Việt offline cục bộ trong repo; chặn formula injection Excel (`=`, `+`, `-`, `@`, `\t`, `\r`).
