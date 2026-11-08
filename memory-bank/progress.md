# Progress Log — không được tự bịa trạng thái

## Snapshot 2026-11-08

| Phase | State | Note |
| --- | --- | --- |
| P0 Foundation | PASS (EG-008 REVIEW) | Code + tests + offline build pass; hardware 2-phone AP pending pilot |
| P1 Roster | PASS | EG-101..EG-107 DONE, 11/11 pytest + 4/4 vitest pass |
| P2 Converter | IN_PROGRESS | Starting EG-201..EG-209 |
| P3 Exam Engine | TODO | Pending P2 |
| P4 Monitoring | TODO | Pending P3 |
| P5 Scores/Receipts | TODO | Pending P4 |
| P6 Paper/OMR | TODO | Optional |
| P7 Release/Pilot | TODO | Pending |

2026-11-08 — P1 (`EG-101`..`EG-107`)
Implemented: Roster CRUD, CSV/XLSX dry-run import, hashed invite codes + rate limit, pending/approve room, single attempt/device binding, cross-student negative tests.
Verification: `tools/verify.ps1` (11/11 pytest, 4/4 vitest, ruff, mypy, eslint, tsc, build PASS).
Evidence paths: `docs/phase-reports/PHASE_P1_REPORT.md`, `backend/tests/test_p1_roster_and_rooms.py`.
Next: P2 (`EG-201`..`EG-209`).
