# Progress Log — không được tự bịa trạng thái

## Snapshot 2026-11-08

| Phase | State | Note |
| --- | --- | --- |
| P0 Foundation | PASS (EG-008 REVIEW) | Code + tests + offline build pass; hardware 2-phone AP pending pilot |
| P1 Roster | PASS | EG-101..EG-107 DONE, 11/11 pytest + 4/4 vitest pass |
| P2 Converter | PASS | EG-201..EG-209 DONE, 16/16 pytest + 4/4 vitest pass |
| P3 Exam Engine | PASS | EG-301..EG-310 DONE, 20/20 pytest + 6/6 vitest pass |
| P4 Monitoring | PASS (EG-407 REVIEW) | EG-401..406, 408 DONE; 22/22 pytest + 8/8 vitest pass; physical 3-phone matrix pending pilot |
| P5 Scores/Receipts | IN_PROGRESS | Starting EG-501..EG-510 |
| P6 Paper/OMR | TODO | Optional |
| P7 Release/Pilot | TODO | Pending |

2026-11-08 — P4 (`EG-401`..`EG-408`)
Implemented: Authenticated WebSocket `/ws/v1/room/{exam_id}`, presence & incident state machine (`0005_monitoring_and_incidents`), configurable grace thresholds, `APP_HIDDEN`/`PAGE_UNLOADED`/`NETWORK_LOST` telemetry, teacher live T6 console & incident resolution drawer (`unlock`, `extend_time`, `terminate` preserving snapshot), student S5 lock/disconnect recovery UI, token refresh & device rebind socket revocation.
Verification: `tools/verify.ps1` (22/22 pytest, 8/8 vitest, ruff, mypy, eslint, tsc, build PASS).
Evidence paths: `docs/phase-reports/PHASE_P4_REPORT.md`, `docs/MONITORING_MATRIX.md`, `backend/tests/test_p4_monitoring.py`.
Next: P5 (`EG-501`..`EG-510`).
