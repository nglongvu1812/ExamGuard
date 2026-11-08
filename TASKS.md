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
| EG-201 | TODO | Validated file ingest, checksum and source immutable storage |
| EG-202 | TODO | DOCX OOXML text/runs/table/content ordering extraction |
| EG-203 | TODO | DOCX images/relationships and floating/inline anchors handling |
| EG-204 | TODO | OMML extraction/MathML local render + snapshot fallback |
| EG-205 | TODO | Question/option segmentation rule engine & provenance |
| EG-206 | TODO | Draft schema/validation/warnings/confidence per field |
| EG-207 | TODO | Split-view original/preview and manual correction UI |
| EG-208 | TODO | Teacher confirmation/key approval, immutable question bank versions |
| EG-209 | TODO | Fixture benchmark report, malformed document security tests |

## P3 — Exam Engine

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-301 | TODO | Exam configure UI/API + invalid state transitions tests |
| EG-302 | TODO | Seeded question/option permutation, score mapping preserved |
| EG-303 | TODO | Room WAITING/RUNNING/CLOSED lifecycle, server timer/pause/resume |
| EG-304 | TODO | Student responsive exam UI, navigation, saved state badges |
| EG-305 | TODO | Transactional answer revisions/idempotency and ACK after commit |
| EG-306 | TODO | HTTP sync canonical answer state after reconnect |
| EG-307 | TODO | Submit snapshot atomic and idempotent |
| EG-308 | TODO | SQLite backup and app restart recovery |
| EG-309 | TODO | Concurrent race tests: start/close/save/submit |
| EG-310 | TODO | E2E 5 fake students, offline, capture logs |

## P4 — Monitoring

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-401 | TODO | Authenticated WS lifecycle/heartbeat/reconnect state |
| EG-402 | TODO | Presence model, server transitions, dashboard status |
| EG-403 | TODO | Visibility/pagehide events collected with server timestamp |
| EG-404 | TODO | Configurable grace period + non-punitive incident model |
| EG-405 | TODO | Teacher lock/unlock/rebind, reason audit |
| EG-406 | TODO | Student technical incident screen and retry handling |
| EG-407 | TODO | Cross-browser real device matrix and false-positive notes |
| EG-408 | TODO | Threat tests, role checks, no cheating guarantees claimed |

## P5 — Results

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-501 | TODO | Pure scoring implementation and unit tests |
| EG-502 | TODO | Key/rubric versioning and regrade run records |
| EG-503 | TODO | Append-only audit events + chain validation |
| EG-504 | TODO | Closed/reviewed/published gate and negative API tests |
| EG-505 | TODO | Student result review UI with own answer vs correct key after publication |
| EG-506 | TODO | Personal PDF receipt + PNG share card with masked PII |
| EG-507 | TODO | Receipt version/supersession after score changes |
| EG-508 | TODO | Excel export with formula injection protection and statistical accuracy |
| EG-509 | TODO | Phúc khảo trace report: exam/answers/key/score/events |
| EG-510 | TODO | E2E publish/regrade/cross-student security tests |

## P6 — Paper/extended converter

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-601 | TODO | Multiple print versions using deterministic mapping |
| EG-602 | TODO | PDF A4 booklet generated offline with math/image fallback |
| EG-603 | TODO | OMR sheet with student and exam code markers |
| EG-604 | TODO | OMR image processing crop/deskew/bubbles with confidence |
| EG-605 | TODO | Teacher review ambiguous OMR and original scan stored |
| EG-606 | TODO | Paper result maps into shared grade history |
| EG-607 | TODO | PDF text/multi-column/vector diagram converter |
| EG-608 | TODO | XLSX import variants/teacher parsing profiles |
| EG-609 | TODO | Benchmark report and optional local OCR feasibility |

## P7 — Release/Pilot

| ID | Status | Definition of Done |
| --- | --- | --- |
| EG-701 | TODO | Portable onedir EXE launch on clean Windows 10 x64 |
| EG-702 | TODO | Windows 11 x64 test + no admin runtime unless firewall permission |
| EG-703 | TODO | No Internet network traffic to external servers during exam |
| EG-704 | TODO | LAN AP/router setup documented + hotspot caveat |
| EG-705 | TODO | 40–50 client load scenario, p50/p95 latency/errors measured |
| EG-706 | TODO | Crash, disk-full, power-loss simulated recoverability tests |
| EG-707 | TODO | Backup/restore migration test on another PC |
| EG-708 | TODO | Signed/hashed release archive with version and changelog |
| EG-709 | TODO | Teacher manual quickstart + troubleshooting |
| EG-710 | TODO | Student quickstart with QR and accessibility/alternative notes |
| EG-711 | TODO | 1–2 teacher pilots with feedback and issue triage |
| EG-712 | TODO | Release checklist license/security/privacy/legal review; label beta if pending |

## Quy tắc cập nhật

Agent bắt đầu một task -> `IN_PROGRESS` + ghi `activeContext`; hoàn tất test và báo cáo -> `REVIEW`; người dùng chấp thuận/gate pass -> `DONE`. Nếu không chạy được test (thiếu Windows/AP/điện thoại), ghi `BLOCKED`, không tự đánh dấu DONE.
