# Architecture Decision Records (ADR)

Mọi ADR mới theo mẫu: `ID — Status — Context — Decision — Alternatives — Consequences — Migration/Test impacts — Approved by`. Không thay đổi ADR đã accepted mà không bổ sung superseding ADR.

## ADR-001 — Single Classroom Mode — Accepted (08/11/2026)

- Context: giáo viên chủ yếu tổ chức 15/45/60 phút cho một lớp; School Mode nhiều phòng đòi hạ tầng/điều phối cao, người dùng xác định khó khả thi local.
- Decision: một host/laptop, một active exam, LAN local; không build multi-host School Mode v1.
- Consequence: đơn giản hóa, giới hạn dùng trong kỳ thi tập trung; hỗ trợ xuất PDF/OMR thay vì điều phối multi-room.

## ADR-002 — Windows Portable + Browser Client — Accepted

- Decision: ứng dụng quản lý Windows Portable và student responsive browser không cần cài app; backend embedded FastAPI; media/static local.
- Tradeoff: browser không khóa hệ điều hành, không đọc MAC, không tự tải file về máy tùy ý.

## ADR-003 — Offline mandatory during exam — Accepted

- Decision: network WAN không cần; local AP/router không WAN là phương án đề nghị; Mobile Hotspot Windows chỉ option sau compatibility check.
- Tradeoff: không cloud push, remote auth, serverless DB, CDN; cần hướng dẫn LAN/firewall.

## ADR-004 — No-account roster-based identity — Accepted

- Decision: roster ID, per-exam one-time invite, teacher approval, attempt token và optional browser binding key.
- Tradeoff: không thể xác minh danh tính thật tuyệt đối bằng phần mềm; cần giám sát tại lớp; browser reset có thể thay binding.

## ADR-005 — Monitoring non-punitive — Accepted

- Decision: heartbeat/visibility best-effort, grace threshold, teacher review. Loss of connectivity is not proof of cheating.
- Tradeoff: người cố tình chuyển mạng có thể phát hiện nhưng không thể ngăn tài liệu offline/4G/thiết bị khác tuyệt đối.

## ADR-006 — Source-preserving Converter — Accepted

- Decision: intermediate rich blocks, source+hash retained, math/diagram fallback image, teacher approval mandatory; deterministic parser before optional AI.
- Tradeoff: một số đề có thể phải sửa tay, không cam kết 100% auto parse.

## ADR-007 — Server-authoritative data — Accepted

- Decision: deadline, score, state, submit, publication phía server; save ACK after transaction commit and idempotency.
- Tradeoff: SQLite writes cần thiết kế cẩn thận; browser UI phải hiển thị pending khi offline.

## ADR-008 — Immutable evidence and late publication — Accepted

- Decision: source answers retained, versioned scoring, audit chain, receipt after entire exam CLOSED + REVIEWED + teacher PUBLISHED.
- Tradeoff: receipt không tự xuất ngay khi một học sinh nộp; sửa điểm sau publish tạo bản mới.

## ADR-009 — Paper alternative — Accepted

- Decision: xuất in giấy, OMR tiếp sau release online core. Không ép học sinh phải có smartphone để có điểm.
- Tradeoff: scope v1 phân kỳ; không xây School Mode.

## ADR-010 — Technology stack — Proposed, confirm at P0

- Choice: FastAPI/Pydantic/SQLAlchemy/SQLite, React/TS/Vite, onedir PyInstaller, pywebview hoặc browser-based teacher UI.
- Before accept: prototype app startup, package size, Windows compatibility, dependency licensing. Keep alternatives in P0 report.

## ADR-011 — AI Converter deployment — Pending user choice

- Default safe: **không cần model AI lớn ở runtime; parser deterministic + media fallback offline**. Optional local AI module P2; external AI opt-in future outside exam process.
- Must get confirmation before uploading question files to third parties or introducing paid remote dependency.

## ADR-012 — Local transport security — Pending technical validation

- Baseline prototype: isolated trusted Wi-Fi + HTTP LAN, short-lived tokens and scope; explicitly document sniffing risk.
- Explore practical local HTTPS provisioning/certificate onboarding before official release; no self-signed warning bypass presented as secure.

## New ADR template

```text
### ADR-NNN — Title — Proposed/Accepted/Superseded
Date / owner:
Context:
Decision:
Alternatives considered:
Consequences:
Security/privacy/fairness impact:
Migration and test plan:
Approval/evidence:
```
