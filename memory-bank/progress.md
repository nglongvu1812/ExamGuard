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
| P7 Release/Pilot | IN_PROGRESS | Starting EG-701..EG-712 |

2026-11-08 — P6 (`EG-601`..`EG-609`)
Implemented: Migration `0007_paper_bridge_and_omr` (`PaperVersion`, `OmrScanSubmission`), deterministic paper variants mapping back to `option_id`, offline A4 booklet & OMR PDFs (`DejaVuSans.ttf` lossless ToUnicode), Pillow+NumPy 8-param homography OMR processor with bubble contrast confidence & `NEEDS_REVIEW` queue, `409 Conflict` online override protection + bridge into shared `GradeRun`/`ScoreVersion`, `pypdf` 2-col/vector/low-text PDF converter & 4-profile XLSX question converter, `/paper` UI & multi-format `/questions` UI.
Verification: `tools/verify.ps1` (29/29 pytest, 11/11 vitest, ruff, mypy, eslint, tsc, build PASS) + live P6 benchmark (PDF 20q 71.3ms, XLSX 50q 58.6ms, OMR -6° rotated 40/40 hits in 161.8ms).
Evidence paths: `docs/phase-reports/PHASE_P6_REPORT.md`, `backend/tests/test_p6_paper_and_converters.py`, `frontend/src/App.test.tsx`.
Next: P7 (`EG-701`..`EG-712`).
