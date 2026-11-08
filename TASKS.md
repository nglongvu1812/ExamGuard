# Task Board — ExamGuard

Các task ban đầu đều `TODO`, trừ khi agent đã thực sự code/test và ghi evidence. Trạng thái hợp lệ: `TODO`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`. Chỉ `DONE` khi acceptance gate có minh chứng.

## P0 — Foundations

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-001 | DONE | Khởi tạo monorepo, Python/Node versions, lockfile, no secrets committed |
| EG-002 | DONE | FastAPI `/health`, Pydantic settings, structured local logging + tests |
| EG-003 | DONE | SQLite WAL, SQLAlchemy, Alembic base migration, DB consistency test |
| EG-004 | DONE | React teacher/student shells, local font/assets, no CDN request |
| EG-005 | DONE | Windows launcher local process lifecycle, graceful shutdown |
| EG-006 | DONE | LAN interface discovery, QR/status, firewall diagnostic guide, no hardcoded IP |
| EG-007 | DONE | CI/local lint/typecheck/tests and test fixture framework |
| EG-008 | REVIEW | Automated offline SPA + LAN API verified; physical 2-phone AP test pending hardware pilot |

## P1 — Roster

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-101 | DONE | Classroom/student CRUD service/API/database + tests |
| EG-102 | DONE | Import CSV/XLSX preview, dry-run duplicate resolution, test malformed sheets |
| EG-103 | DONE | Teacher roster UI with search/edit/archive and history preservation |
| EG-104 | DONE | Random invite codes hashed, expiry and rate limiting |
| EG-105 | DONE | Student join pending + teacher approval UI + race test |
| EG-106 | DONE | One active attempt/student + browser binding/revoke/rebind audit |
| EG-107 | DONE | Unauthorized cross-student API access negative test |

## P2 — Converter

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-201 | DONE | Validated file ingest, checksum and source immutable storage |
| EG-202 | DONE | DOCX OOXML text/runs/table/content ordering extraction |
| EG-203 | DONE | DOCX images/relationships and floating/inline anchors handling |
| EG-204 | DONE | OMML extraction/MathML local render + snapshot fallback |
| EG-205 | DONE | Question/option segmentation rule engine & provenance |
| EG-206 | DONE | Draft schema/validation/warnings/confidence per field |
| EG-207 | DONE | Split-view original/preview and manual correction UI |
| EG-208 | DONE | Teacher confirmation/key approval, immutable question bank versions |
| EG-209 | DONE | Fixture benchmark report, malformed document security tests |

## P3 — Exam Engine

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-301 | DONE | Exam configure UI/API + invalid state transitions tests |
| EG-302 | DONE | Seeded question/option permutation, score mapping preserved |
| EG-303 | DONE | Room WAITING/RUNNING/CLOSED lifecycle, server timer/pause/resume |
| EG-304 | DONE | Student responsive exam UI, navigation, saved state badges |
| EG-305 | DONE | Transactional answer revisions/idempotency and ACK after commit |
| EG-306 | DONE | HTTP sync canonical answer state after reconnect |
| EG-307 | DONE | Submit snapshot atomic and idempotent |
| EG-308 | DONE | SQLite backup and app restart recovery |
| EG-309 | DONE | Concurrent race tests: start/close/save/submit |
| EG-310 | DONE | E2E 5 fake students, offline, capture logs |

## P4 — Monitoring

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-401 | DONE | Authenticated WS lifecycle/heartbeat/reconnect state |
| EG-402 | DONE | Presence model, server transitions, dashboard status |
| EG-403 | DONE | Visibility/pagehide events collected with server timestamp |
| EG-404 | DONE | Configurable grace period + non-punitive incident model |
| EG-405 | DONE | Teacher lock/unlock/rebind, reason audit |
| EG-406 | DONE | Student technical incident screen and retry handling |
| EG-407 | REVIEW | Cross-browser matrix & false-positive guide (`docs/MONITORING_MATRIX.md`); physical 3-phone test pending hardware pilot |
| EG-408 | DONE | Threat tests, role checks, no cheating guarantees claimed |

## P5 — Results

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-501 | DONE | Pure scoring implementation and unit tests |
| EG-502 | DONE | Key/rubric versioning and regrade run records |
| EG-503 | DONE | Append-only audit events + chain validation |
| EG-504 | DONE | Closed/reviewed/published gate and negative API tests |
| EG-505 | DONE | Student result review UI with own answer vs correct key after publication |
| EG-506 | DONE | Personal PDF receipt + PNG share card with masked PII |
| EG-507 | DONE | Receipt version/supersession after score changes |
| EG-508 | DONE | Excel export with formula injection protection and statistical accuracy |
| EG-509 | DONE | Phúc khảo trace report: exam/answers/key/score/events |
| EG-510 | DONE | E2E publish/regrade/cross-student security tests |

## P6 — Paper/extended converter

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-601 | DONE | Multiple print versions using deterministic mapping |
| EG-602 | DONE | PDF A4 booklet generated offline with math/image fallback |
| EG-603 | DONE | OMR sheet with student and exam code markers |
| EG-604 | DONE | OMR image processing crop/deskew/bubbles with confidence |
| EG-605 | DONE | Teacher review ambiguous OMR and original scan stored |
| EG-606 | DONE | Paper result maps into shared grade history |
| EG-607 | DONE | PDF text/multi-column/vector diagram converter |
| EG-608 | DONE | XLSX import variants/teacher parsing profiles |
| EG-609 | DONE | Benchmark report and optional local OCR feasibility |

## P7 — Release/Pilot

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-701 | REVIEW | Portable onedir EXE built & cold-boot verified on Windows 11; separate clean Win10 x64 PC test pending field pilot |
| EG-702 | DONE | Windows 11 x64 tested + non-admin runtime verified without elevation |
| EG-703 | DONE | Zero Internet network traffic / zero external CDN requests verified statically & dynamically |
| EG-704 | DONE | LAN AP/router guide documented (`docs/LAN_AP_GUIDE.md`) + Hotspot caveats & firewall |
| EG-705 | DONE | 45-client concurrent load benchmark measured (`tools/load_test.py`, 3 runs, p95=727.9ms, 0 lost ACK) |
| EG-706 | DONE | Simulated disk-full (HTTP 507) & permission denied tests preserve live DB (`test_p7_resilience_and_recovery.py`) |
| EG-707 | DONE | Mid-exam crash restart WAL recovery & cross-PC full restore test verified |
| EG-708 | DONE | SHA-256 hashed release archive `ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.55 MB) + CHANGELOG |
| EG-709 | DONE | Teacher quickstart manual with 5-step workflow & troubleshooting (`docs/TEACHER_QUICKSTART.md`) |
| EG-710 | DONE | Student quickstart guide with QR, offline Wi-Fi & paper alternative (`docs/STUDENT_QUICKSTART.md`) |
| EG-711 | REVIEW | Pilot protocol with 1–2 teachers prepared in runbook; real classroom feedback pending field trial |
| EG-712 | DONE | Release checklist license audit (59 libs, 0 AGPL), privacy review & Beta status established (`docs/RELEASE_CHECKLIST.md`) |

## Quy tắc cập nhật

Agent bắt đầu một task -> `IN_PROGRESS` + ghi `activeContext`; hoàn tất test và báo cáo -> `REVIEW`; người dùng chấp thuận/gate pass -> `DONE`. Nếu không chạy được test (thiếu Windows/AP/điện thoại), ghi `BLOCKED`, không tự đánh dấu DONE.
