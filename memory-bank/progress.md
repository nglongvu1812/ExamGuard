# Progress Log — không được tự bịa trạng thái

## Snapshot 2026-11-08

| Phase | State | Note |
| --- | --- | --- |
| P0 Foundation | PASS (EG-008 REVIEW) | Code + tests + offline build pass; hardware 2-phone AP pending pilot |
| P1 Roster | PASS | EG-101..EG-107 DONE, 11/11 pytest + 4/4 vitest pass |
| P2 Converter | PASS | EG-201..EG-209 DONE, 16/16 pytest + 4/4 vitest pass |
| P3 Exam Engine | IN_PROGRESS | Starting EG-301..EG-310 |
| P4 Monitoring | TODO | Pending P3 |
| P5 Scores/Receipts | TODO | Pending P4 |
| P6 Paper/OMR | TODO | Optional |
| P7 Release/Pilot | TODO | Pending |

2026-11-08 — P2 (`EG-201`..`EG-209`)
Implemented: Safe DOCX ingest (zip-bomb/traversal/XXE/external image guard), OOXML ordered blocks & 2x2 tables, OMML->LaTeX + raw XML, non-guessing segmentation, Split-View Review UI + KaTeX offline render, immutable QuestionVersion/AnswerKeyVersion approval.
Verification: `tools/verify.ps1` (16/16 pytest, 4/4 vitest, ruff, mypy, eslint, tsc, build PASS).
Evidence paths: `docs/phase-reports/PHASE_P2_REPORT.md`, `backend/tests/test_p2_converter.py`.
Next: P3 (`EG-301`..`EG-310`).