# Progress Log — không được tự bịa trạng thái

## Snapshot 2026-11-08

| Phase | State | Note |
| --- | --- | --- |
| P0 Foundation | PASS (EG-008 REVIEW) | Code + tests + offline build pass; hardware 2-phone AP pending pilot |
| P1 Roster | PASS | EG-101..EG-107 DONE, 11/11 pytest + 4/4 vitest pass |
| P2 Converter | PASS | EG-201..EG-209 DONE, 16/16 pytest + 4/4 vitest pass |
| P3 Exam Engine | PASS | EG-301..EG-310 DONE, 20/20 pytest + 6/6 vitest pass |
| P4 Monitoring | IN_PROGRESS | Starting EG-401..EG-408 |
| P5 Scores/Receipts | TODO | Pending P4 |
| P6 Paper/OMR | TODO | Optional |
| P7 Release/Pilot | TODO | Pending |

2026-11-08 — P3 (`EG-301`..`EG-310`)
Implemented: Exam wizard & lifecycle state machine, deterministic seeded permutation keeping option_id, server timer + pause/resume, commit-before-ACK idempotent AnswerRevision + canonical HTTP sync, atomic Submission snapshot, hot SQLite + archive backup/restore, StudentExamPage + SettingsBackupPage.
Verification: `tools/verify.ps1` (20/20 pytest, 6/6 vitest, ruff, mypy, eslint, tsc, build PASS).
Evidence paths: `docs/phase-reports/PHASE_P3_REPORT.md`, `backend/tests/test_p3_exam_engine.py`.
Next: P4 (`EG-401`..`EG-408`).