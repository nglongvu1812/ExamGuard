# MASTER PLAN — Phát triển ExamGuard bằng AI Agent

> Mục tiêu: một người phát triển, agent hỗ trợ code. Tổng 16–22 tuần tùy nền tảng và độ ổn định; không coi timeline là cam kết. Phải qua gate trước khi sang phase kế.

## Phương pháp làm việc

- Mỗi phase gồm `analyse -> design -> implement vertical slice -> tests -> manual demo -> docs -> gate`.
- Task phải hoàn thành nhỏ theo chiều dọc (API + DB + UI + test), tránh xây toàn bộ backend trước rồi mới frontend.
- Mọi task cần acceptance, negative case, screenshot/UI demo và log test.
- Build CI local (lint,typecheck,test) từ đầu; fixture giả không chứa PII; commit nhỏ sau khi pass.
- Không tối ưu AI converter phức tạp trước khi exam transaction/reliability đủ vững.

## P0 — Repository, skeleton, local runtime (tuần 1–2)

**Deliverables:** repo structure; backend hello+health; React teacher/student shell static bundled; launcher chạy server/đóng đúng; config data path; Python/Node lockfile; SQLite migrations; logging; tests/CI local.

**Tasks:** EG-001..EG-008.

**Gate P0:** chạy app + mobile LAN thử với 2 điện thoại, không cần Internet; ngắt Internet website còn load 100% assets; health; migration từ clean data; launcher dừng server. User chấp thuận hướng shell pywebview/browser.

## P1 — Classrooms & roster identity (tuần 3–4)

**Deliverables:** CRUD class/student, import Excel/CSV dry-run, duplicate conflict report, logical archive; exam invite token, join pending, teacher approve, one attempt/student, device browser binding best effort.

**Tasks:** EG-101..EG-107.

**Gate P1:** giáo viên import 40 học sinh giả, cập nhật 2 tên không đổi mã; 2 thiết bị login cùng một student không tạo hai attempt; teacher reset ghi audit; client B không thấy dữ liệu A.

## P2 — Converter v1 Word and question bank (tuần 5–7)

**Deliverables:** import DOCX text/paragraph/table/image/OMML, content blocks, original file store, source mapping, preview split view, warnings, manual key confirmation, approved immutable question version. Simple PDF text/PDF crop là mục tiêu phụ sau DOCX gate.

**Tasks:** EG-201..EG-209.

**Gate P2:** bộ fixture DOCX thường, bảng, ảnh, công thức render không mất thành phần; key không khai báo được flag; preview và approved version; test import file lỗi an toàn. Báo tỉ lệ parse đúng theo nhóm chứ không ép 100%.

## P3 — Exam engine, timer, answer integrity (tuần 8–10)

**Deliverables:** create exam, immutable permutation by seed, state machine, server timer, student quiz UI, answer autosave+ACK+revision, submit idempotent, recovery after restart, DB backup.

**Tasks:** EG-301..EG-310.

**Gate P3:** từ import đề 20 câu → teacher mở phòng → 5 học sinh thi → nộp; tắt/restart server giữa bài mà không mất ACKed answers; double submit safe; clock tamper client no effect; answer key không có trong API student.

## P4 — Realtime monitoring & security/fairness (tuần 11–12)

**Deliverables:** WebSocket reconnect, presence dashboard, heartbeats, `visibilitychange`, incident, grace policy, lock/unlock and teacher review. Token refresh and expiration.

**Tasks:** EG-401..EG-408.

**Gate P4:** ở 3 loại điện thoại/browsers (nếu có), thử chuyển app, reload, ngắt Wi-Fi, chuyển Wi-Fi, bật 4G, 15s timeout; không false claim; reconnect/resync; teacher xử lý sự cố; role/API negative tests.

## P5 — Scoring, audit, publication, receipts (tuần 13–15)

**Deliverables:** deterministic scoring, key/rubric version, score/version, audit log, review/publish gate, responsive student result review, downloadable PDF/PNG, export Excel, phúc khảo.

**Tasks:** EG-501..EG-510.

**Gate P5:** không lấy được đáp án trước publish; sau `CLOSED + REVIEWED + PUBLISHED` tải receipt đúng identity; sửa key tạo regrade và lịch sử, old receipt superseded; Excel totals match DB; audit event hash check.

## P6 — Paper bridge + extended converter (tuần 16–18, optional gate)

**Deliverables:** PDF multi-version printed exam, answer mapping, OMR answer sheet and scan desktop (nếu đủ khả năng), PDF text import, XLSX/question profile, optional local OCR on selected dataset.

**Tasks:** EG-601..EG-609.

**Gate P6:** output print A4 đúng, đáp án mapping after shuffle; OMR nhận rõ, flag ambiguous (không guess), save original scan, teacher approve corrections; benchmark converter theo từng kiểu.

Nếu P0–P5 chưa ổn định thì **hoãn P6**, không chạy nhiều mô-đun yếu song song.

## P7 — Packaging, load test, pilot, release (tuần 19–22)

**Deliverables:** onedir Windows build, no external runtime dependency, user guide, automatic backup/restore test, firewall walkthrough, no-Internet packet check, 40–50 concurrent load test on real AP/laptop, bugfix, privacy/release checklist, 1–2 teacher pilots.

**Tasks:** EG-701..EG-712.

**Gate P7:** all P0 requirements pass; measured p95/reject/error rate attached; cold boot Windows test; run offline on fresh machine; backup restore; known limitations documented; release version/tag and checksums. Nếu fail => beta không dùng lấy điểm chính thức.

## Milestone báo cáo đồ án

| Milestone | Minh chứng bắt buộc |
| --- | --- |
| M1 architecture | ERD, state machine, threat model, ADR, simple LAN demo |
| M2 converter | Benchmark source vs parsed, images/OMML preview, review UI |
| M3 stable exam | 5-user E2E, crash/reconnect, autosave and submit integrity |
| M4 monitoring | incident timeline, false-positive case, teacher recovery |
| M5 results | receipt, score/version changes, before/after publish test |
| M6 real pilot | 40–50 load chart/log, teacher usability feedback, installer/portable demo |

## Stop conditions

- Chưa chốt answers identity/mapping: không triển khai shuffle/scoring.
- Không pass test no early answer leak: không cho pilot.
- Có tình huống ACK rồi mất dữ liệu sau restart: dừng feature work, sửa persistence.
- Bài exam chính thức có thể tự đổi đáp án/điểm không audit: dừng release.
- Không đủ điều kiện LAN/router: giảm target bench/scope, không fake số tải.
- Thiếu máy/học sinh thật để pilot: báo giới hạn, không gọi demo giả là field trial.
