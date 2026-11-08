# Risk Register

Likelihood/Impact: Low / Medium / High. Owner mặc định: lead developer. Cập nhật khi có dữ liệu thực tế.

| ID | Risk | L | I | Mitigation | Stop/escalation |
| --- | --- | --- | --- | --- | --- |
| R01 | Không đủ 40–50 kết nối hotspot | High | High | AP/router offline riêng, benchmark thiết bị thật | không quảng cáo capacity nếu chưa đo |
| R02 | Browser hạ heartbeat khi background | High | High | grace threshold, visibility event, manual review, cross-browser tests | false-positive vượt ngưỡng thì bỏ auto-lock |
| R03 | Mất dữ liệu khi restart/crash | Medium | Critical | ACK after COMMIT, WAL, backup, crash tests | block release ngay |
| R04 | Parser làm sai công thức/ảnh | High | High | source-preserving fallback, side by side review, fixture benchmark | không cho đề chưa duyệt vào thi |
| R05 | Lộ đáp án trước kết thúc | Medium | Critical | API/RBAC tests, no key in payload/source/WS | block release ngay |
| R06 | Giả danh/thay thiết bị | High | Medium | one attempt, per-student invite, teacher approval, audit | không claim chống gian lận tuyệt đối |
| R07 | Plain HTTP LAN bị nghe lén | Medium | High | trusted AP, scope/expiry, HTTPS feasibility | không claim secure-grade release |
| R08 | Người có quyền máy sửa DB + hash | Medium | High | audit, backup/external anchor option | không claim tamper-proof tuyệt đối |
| R09 | Không có điện thoại/thiết bị | High | High | paper alternative, trial opt-in, school arrangements | không ép thiết bị cá nhân |
| R10 | Thi chính thức sai quy trình trường | Medium | Critical | school approval, pilot non-grade, regulatory review | không triển khai lấy điểm khi chưa được chấp thuận |
| R11 | OMR quét sai do ánh sáng/tô mờ | High | High | calibration, confidence, human review, keep source scan | không chấm tự động không giám sát với input mơ hồ |
| R12 | Scope creep School Mode/multi-cloud | High | Medium | frozen Classroom Mode scope, ADR review | hoãn ngoài v1 |
| R13 | Portable bị antivirus chặn/hỏng runtime | Medium | High | clean PC tests, signed build in future, onedir, logs | beta khi build chưa ổn |
| R14 | Dependency license không phù hợp | Medium | Medium | inventory SPDX/license check, alternatives | review trước distribution |
| R15 | Thời gian một coder không đủ | High | High | P0–P5 ưu tiên, P6 optional, task vertical slices | giảm features trước khi giảm tests |
| R16 | Dữ liệu cá nhân bị lộ qua backup/exports | Medium | High | encryption option, access controls, PII minimization, retention | không dùng dữ liệu thật nếu chưa có chính sách |

## Weekly risk review

- Có incident mới hay không? Ghi reproducible steps.
- Risk score tăng/giảm theo số đo nào?
- Mitigation có test mới không?
- Feature nào cần tạm dừng để khôi phục tính đúng đắn?
