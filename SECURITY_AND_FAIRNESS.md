# Security, Threat Model và chính sách công bằng

## 1. Ranh giới tin cậy

- Server local thuộc laptop giáo viên: nguồn xác thực tính điểm/timer/trạng thái.
- Student browser và điện thoại **không đáng tin**: có thể refresh, sửa JS, đổi mạng, bật 4G, chia đôi màn hình, fake event, dùng máy khác.
- LAN có thể bị sniff/spoof nếu không mã hóa/chặn; không giả định Wi-Fi chung là secure.
- Người có quyền admin vật lý trên laptop có thể sửa cả DB và audit; không tuyên bố chống giả mạo tuyệt đối.
- Import document không tin cậy: malware, zip bomb, XML entity, path traversal, scripts, data exfiltration.

## 2. Threat model table

| Threat | Biện pháp | Giới hạn |
| --- | --- | --- |
| Hai thiết bị vào cùng mã học sinh | one active attempt + teacher approval + revoke/rebind | Có thể mượn tài khoản lúc chưa duyệt nếu thông tin bị lộ |
| Một điện thoại nhiều tài khoản | browser binding key/token per exam; duplicate detection | Xóa dữ liệu/browser khác bypass; không thể chứng minh cùng phần cứng |
| Đổi Wi-Fi, mất mạng | heartbeat/presence timeout, grace period, teacher review | Nhiễu sóng/trình duyệt nền cũng gây timeout |
| Rời trang đọc tài liệu | visibilitychange/pagehide event + log | Không phát hiện chắc split-screen, overlay, background tricks |
| 4G/thiết bị thứ hai | giám sát lớp, đảo đề, chính sách coi thi | Website không thể chặn hoàn toàn |
| Chụp màn hình | bảo vệ nội dung đề, đảo đề, thông báo quy định | Trình duyệt không chặn chắc chắn |
| Đoán mã đăng nhập | random one-time codes, rate limiting, TTL, teacher approval | Thông tin bị chia sẻ vẫn có thể lộ |
| API truy xuất đáp án sớm | server auth + status gates + negative tests | phải test cả error response, WebSocket payload |
| Sửa điểm trong UI | immutable submissions, score versions, audit, reason | Full admin disk access vẫn sửa được cả chain |
| AI đổi nội dung câu hỏi | compare source, review, content snapshot/version | human review cũng có sai sót |
| Sập server/mất điện | commit before ACK, consistent backup, resume | pending chưa ACK có thể mất; phải hiển thị rõ |
| XSS/CSRF/file injection | CSP, strict sanitization, MIME/size checks, safe filenames | phụ thuộc implementation/test |
| Chiếm token qua HTTP LAN | network segregation, token scope/TTL, HTTPS plan | plain HTTP không mã hóa; rủi ro có thật |

## 3. Policy giám sát được cấu hình

Phân biệt events `APP_HIDDEN`, `PAGE_UNLOADED`, `HEARTBEAT_TIMEOUT`, `NETWORK_LOST`, `CLIENT_RELOAD`, `DUPLICATE_ATTEMPT`, `TEACHER_REBIND`.

Đề xuất mốc mặc định để **thử nghiệm**: heartbeat 3s, nghi mất 5s, xác nhận disconnected 15s. Không hardcode: cấu hình ở UI, theo dõi false positive trên iPhone/Android. Nếu lỗi kỹ thuật, giáo viên có lựa chọn resume, extend time, paper fallback, invalidate/retest. Không thể định tội gian lận bằng một event.

Luồng lock:

```text
ACTIVE --missed heartbeats--> SUSPECTED --> DISCONNECTED
                                         \-> RECONNECTED (healthy)
DISCONNECTED --policy threshold--> LOCKED_PENDING_REVIEW
LOCKED_PENDING_REVIEW --teacher approve--> ACTIVE
LOCKED_PENDING_REVIEW --teacher terminate--> ENDED_WITH_REVIEW
```

Student view giải thích nguyên nhân, giờ server, trạng thái lưu đáp án, cách báo giáo viên; teacher view hiển thị evidence và nút phân giải. Không làm silent auto-fail.

## 4. Identity và privacy

`StudentID` UUID từ roster, `ExamInviteCode` random per student/exam, `AttemptToken` ngắn hạn; teacher duyệt hiện diện. Browser-generated WebCrypto key + challenge response có thể tăng độ ràng buộc **trong một trình duyệt**, nhưng không đại diện IMEI/MAC/identity vật lý. Browser MAC không truy cập được. Không dùng fingerprint entropy cao như định danh bí mật.

Tùy AP có thể thống kê MAC/IP đang nối, nhưng MAC randomization, NAT, MAC spoof làm kết luận không đáng tin; không lưu lâu dài nếu không cần và không lấy đó làm chế tài.

## 5. Scoring and receipts

Chỉ server chấm từ snapshots; không gửi answer key đến client trước publish. Tách dữ liệu riêng từng học sinh qua auth. Teacher sửa key/điểm cần nhập reason, tạo version, nếu published thì tạo receipt mới và thông báo bản cũ bị thay. Receipt có mã, digest; QR chỉ hỗ trợ tra cứu local. Muốn verify độc lập cần chữ ký tin cậy hoặc external checkpoint.

## 6. Chính sách trường và người chưa có thiết bị

Đây là công cụ hỗ trợ, không tự đủ điều kiện thi chính thức. Cho phép printed alternative, hỗ trợ học sinh khuyết tật/không có smartphone, fallback khi sự cố. Quy định về thi định kỳ và tính pháp lý dữ liệu điện tử phải được đối chiếu theo thời điểm phát hành với văn bản Bộ GD&ĐT/nhà trường. Không ép dùng điện thoại riêng, không ghi âm/quay hình nếu chưa có cơ sở, phạm vi, sự đồng ý và quy trình bảo vệ dữ liệu.

## 7. Mandatory security tests

1. Student GET key ở DRAFT/RUNNING/CLOSED/REVIEWED -> 403/404 không rò qua body/log.
2. Student A GET receipt B -> từ chối.
3. Submit cùng idempotency 20 lần -> một submission.
4. Attempt đến hạn do server -> không nhận answer sau cutoff ngoài recovery policy.
5. Double join/cross-device/revoked token -> từ chối rõ; teacher rebind có audit.
6. Upload zip bomb, malformed DOCX, HTML injected MathML, formula injected Excel -> an toàn.
7. DB rollback/crash sau ACK -> đáp án tồn tại khi restart.
8. Audit manual score change -> reason, actor, version, old/new hash.
9. Không có Internet -> giáo viên/học sinh vẫn thi, không external requests.
