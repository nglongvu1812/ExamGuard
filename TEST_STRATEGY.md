# Test Strategy — ExamGuard

## 1. Nguyên tắc

Không có kiểm thử tự động chỉ chứng minh được *UI đã render*, không chứng minh hệ thống thi đáng tin cậy. Mỗi task có positive + negative tests. Kịch bản cần data giả, reproducible seed, server clock controlled. Test là điều kiện release.

## 2. Test layers

| Tầng | Tool đề xuất | Kiểm tra |
| --- | --- | --- |
| Domain unit | pytest | FSM, scoring, seed permutations, timeout, grade versioning |
| API/integration | pytest + httpx + SQLite temp | auth, transaction, idempotency, RBAC, migrations |
| Converter | pytest fixture/golden JSON/images | segmented positions, equation/media fidelity |
| UI | Vitest/RTL | React flows, error states, accessibility |
| Browser E2E | Playwright desktop/mobile simulation | roster to room, answers, publish, download |
| Manual real device | iOS Safari/Android Chrome/Firefox | background throttling, LAN, QR, download behavior |
| Load | Locust/k6 and real AP | 40–50 clients + save/heartbeat/submit burst |
| Security | scripted negative tests | token isolation, key leaks, malicious files, injection |
| Recovery | process kill/DB snapshot/storage full | ACK durability, backup/restore, migration rollback |

## 3. Required acceptance scenarios

| Test ID | Given / When | Expected |
| --- | --- | --- |
| T-001 | Internet disabled; teacher+phones same LAN | Fully loaded UI, exam create/join/submit without external calls |
| T-002 | Teacher imports roster duplicate ID | Dry-run conflict; never silently merge students |
| T-003 | Student joins twice from two browsers | Single active attempt; teacher decides rebind |
| T-004 | Student guesses another attempt ID | 403/404 no leak, audit/rate limit as appropriate |
| T-005 | Student device clock +2h | Remaining time unchanged (server authoritative) |
| T-006 | 20 rapid answer writes, same idempotency | Exactly one logical write per key; server ordering deterministic |
| T-007 | Response ACK then server process kill | Reload returns last ACKed answer |
| T-008 | Browser offline during unsaved selection | UI shows pending; no false “saved” message |
| T-009 | Wi-Fi disconnect for 7s vs 18s | Configurable suspected/locked; teacher can resolve, correct event source |
| T-010 | App switch/page hidden | Best-effort detection; log timestamp, not auto cheat verdict |
| T-011 | Browser closes/reopens | Attempt sync without duplicate or timer reset |
| T-012 | Student submits twice or during close race | Immutable single submission, no duplicate score |
| T-013 | Student GET key/score before publish | Never returns key, score, or key mapping in any response/event |
| T-014 | Session CLOSED but not REVIEWED | No receipt; teacher review required |
| T-015 | Publish after review | Only own student can download correct version |
| T-016 | Teacher changes key after publish | New grade run, receipts superseded, events/reason retained |
| T-017 | DOCX with OMML image in option | Correspondence correct after shuffle; rendered original comparison |
| T-018 | PDF with vector plot/two columns | No silently dropped diagram; crop or explicit warning |
| T-019 | DOCX without answer key | Cannot auto-approve as complete without teacher supplying key |
| T-020 | OMR double marked/faint box | Human review flag; no silent random choice |
| T-021 | Restore backup on another PC | Record counts/assets/checksums and latest score versions match |
| T-022 | CSV/XLSX malicious `=SUM(...)` user name | Export cell treated as string, no formula execution |
| T-023 | Student requests `../../...` file path | Access blocked and logged safely |
| T-024 | All students submit early | Answer disclosure still waits for teacher closing/review/publish |

## 4. Converter fixture baseline

Create 25 simple docx text variants, 25 DOCX table + style variants, 20 docx math, 10 docx image, 10 PDF vector/multi-column and 10 scan cases as target corpus (>=100). Initially implement representative 2–5 per category; expand gradually. Each expected JSON hand validated. Compare field-level accuracy. Report every failure and fallback reason.

Do not create random percentages; show denominator, false positives and confidence intervals when reporting results. A safe fallback image counts **preserved content**, not success in semantic equation parsing.

## 5. Network and load benchmark

**Setup:** laptop model, CPU/RAM, Windows build, Python build, AP model/band/channel, number of phones, browser versions, Wi-Fi RSSI approximate, room conditions. Record scenario, replicate 3 runs.

**Workload:** 40–50 clients join within 2 min; 20–60 questions, heartbeat 3s, 1 save/5s/client during peak, burst 50 submits at end, 5 reconnect cycles, server restart controlled. Measure API p50/p95/p99, 5xx, timeouts, DB busy/lock, CPU/RAM, RSSI/disconnect, retained submissions. Do not claim result if simulated clients only, label `synthetic` vs `real device`.

**Targets for engineering (not guarantee):** 0 lost ACKed answers; 0 cross-student leakage; 0 premature key leaks; p95 save <1s on stable LAN; <1% accidental disconnect under intended AP conditions (measured); 100% receipt version correct. P95 missing target blocks *release claims*, not necessarily thesis prototype.

## 6. Manual usability pilot

2 teachers in controlled demo, anonymized feedback. Tasks: import 40 students, import DOCX 20q, correct 2 warnings, start session, identify one disconnect, publish and export. Record completion time, number of errors, assistance required, suggestions. Do not involve student PII before consent/school permission.

## 7. Gate report template

```text
Phase: P?
Commit/version:
Tests executed (exact commands):
Passed/failed/skipped:
Manual real-device evidence:
NFR numbers and environment:
Security negative tests:
Outstanding blockers:
Ready for next phase? YES/NO with reason:
```
