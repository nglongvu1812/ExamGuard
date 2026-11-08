# Progress Log — không được tự bịa trạng thái

## Snapshot 2026-11-08

| Phase | State | Note |
| --- | --- | --- |
| P0 Foundation | PASS (EG-008 REVIEW) | Code + tests + offline build pass; hardware 2-phone AP pending pilot |
| P1 Roster | IN_PROGRESS | Starting EG-101..EG-107 |
| P2 Converter | TODO | Pending P1 |
| P3 Exam Engine | TODO | Pending P2 |
| P4 Monitoring | TODO | Pending P3 |
| P5 Scores/Receipts | TODO | Pending P4 |
| P6 Paper/OMR | TODO | Optional |
| P7 Release/Pilot | TODO | Pending |

2026-11-08 — P0 (`EG-001`..`EG-008`)
Implemented: Monorepo, FastAPI health/network/QR, SQLite WAL + Alembic, React Teacher/Student offline shells, Windows launcher, verify script.
Verification: `tools/verify.ps1` + `pytest` (6/6 passed, frontend 2/2 passed, build ok).
Evidence paths: `docs/phase-reports/PHASE_P0_REPORT.md`, `backend/tests/test_p0_foundation.py`, `frontend/src/App.test.tsx`.
Next: P1 (`EG-101`..`EG-107`).
