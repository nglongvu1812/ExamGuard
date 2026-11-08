# Báo cáo Nghiệm thu Kỹ thuật Phase P7 — Đóng gói Windows Portable, Kiểm thử Tải, Phục hồi Thảm họa & Tài liệu Phát hành Beta

> Tài liệu tổng kết Phase P7 theo đúng cấu trúc mục 5 của Quy chuẩn Điều khiển Dự án ExamGuard.

---

## 5.1. Tổng quan

- **Tên Phase:** Phase P7 — Đóng gói Windows Portable, Kiểm thử Tải & Khả năng Phục hồi, Tài liệu Vận hành & Phát hành Thử nghiệm (`Release / Pilot`).
- **Phiên bản phát hành:** `v0.1.0-beta.1` (**Classroom Mode — Single Laptop LAN Offline-First**).
- **Mục tiêu:**
  1. Đóng gói hoàn chỉnh ứng dụng di động Windows Portable `onedir` (`ExamGuard.exe`), không bắt buộc cài đặt, tự tạo và quản lý dữ liệu trong thư mục độc lập `ExamGuardData` cạnh tệp thực thi.
  2. Xác minh hoạt động ngoại tuyến 100% không Internet, không CDN ngoài, không rò rỉ lưu lượng WAN (`0 outbound WAN connections`).
  3. Đo kiểm benchmark tải dồn dập 40–50 học sinh ảo (`tools/load_test.py`) với 3 lượt lặp kiểm chứng độ trễ p50/p95, mức tiêu thụ tài nguyên và cam kết **không mất đáp án đã ACK** (`0 lost ACK`).
  4. Kiểm thử tự động khả năng chống chịu sự cố: ngắt app đột ngột giữa giờ thi, ghi nhận an toàn sau khởi động lại với SQLite WAL, xử lý an toàn khi ổ đĩa bị từ chối quyền ghi hoặc đầy dung lượng sao lưu (`HTTP 507`), và di trú toàn bộ CSDL + tệp tin sang máy tính sạch thứ hai (`Cross-PC restore`).
  5. Biên soạn trọn bộ tài liệu vận hành cho giáo viên, học sinh, hướng dẫn router AP / Wi-Fi lớp học, nhật ký thay đổi và kiểm kê bản quyền/pháp lý trước phát hành.
- **Danh sách Task & Trạng thái hoàn thành:**
  - `EG-701`: **REVIEW** — Biên dịch thành công gói Portable onedir `ExamGuard.exe` chạy độc lập; đã kiểm thử thực tế trên Windows 11 x64; hạng mục kiểm thử trên máy Windows 10 x64 cài sạch riêng biệt giữ trạng thái `REVIEW` phục vụ bước pilot thực địa.
  - `EG-702`: **DONE** — Khởi chạy lạnh thành công `ExamGuard.exe` trên Microsoft Windows 11 Pro Build 28000; ứng dụng chạy bình thường trong ngữ cảnh người dùng không đặc quyền (non-admin), chỉ kích hoạt hộp thoại Windows Firewall mở cổng LAN nội bộ.
  - `EG-703`: **DONE** — Kiểm toán tĩnh toàn bộ mã nguồn build `dist/` và kiểm toán động qua `Get-NetTCPConnection` trên tiến trình đang chạy xác nhận **0 kết nối WAN** và không tải bất kỳ tài nguyên CDN ngoài nào.
  - `EG-704`: **DONE** — Soạn thảo tài liệu `docs/LAN_AP_GUIDE.md` phân tích kiến trúc Router/AP độc lập, cảnh báo giới hạn của Windows Mobile Hotspot và hướng dẫn mở Firewall.
  - `EG-705`: **DONE** — Triển khai công cụ `tools/load_test.py`; chạy thực nghiệm 3 lượt lặp kịch bản 45 học sinh ảo đồng thời: 0 lỗi ACK, 45/45 bài nộp lưu trữ bền vững, độ trễ lưu đáp án `p95 = 727.9 ms` (< 1.0s), RAM tiến trình máy chủ ~5.21 MB.
  - `EG-706`: **DONE** — Kiểm thử tự động `backend/tests/test_p7_resilience_and_recovery.py` chứng minh CSDL không hỏng khi giả lập `PermissionError` ghi dữ liệu hoặc `ENOSPC` (hết dung lượng ổ đĩa khi nén sao lưu trả `HTTP 507`).
  - `EG-707`: **DONE** — Kiểm thử tự động sập ứng dụng giữa kỳ thi, bật lại máy chủ bảo toàn toàn bộ câu trả lời đã ACK qua WAL, và khôi phục toàn vẹn bản sao lưu sang thư mục máy tính thứ hai (`PC2_CleanMachineData`) giữ nguyên điểm, ảnh đề, ảnh OMR và chuỗi chữ ký kiểm toán `AuditEvent`.
  - `EG-708`: **DONE** — Tự động sinh gói phát hành `dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip` (47.66 MB) kèm tệp chữ ký băm `ExamGuard-v0.1.0-beta.1-win64-portable.zip.sha256` (`82c0803b96feb0cdcd3e5e8aef7419bf207f46139db70bade8f9ab5a7fb1edec`), tệp khởi chạy nhanh `ExamGuard.bat`, các bộ đề/phiếu/danh sách mẫu trong `samples/` và `CHANGELOG.md`.
  - `EG-709`: **DONE** — Soạn thảo `docs/TEACHER_QUICKSTART.md` hướng dẫn quy trình 5 bước tổ chức kiểm tra và xử lý sự cố thường gặp.
  - `EG-710`: **DONE** — Soạn thảo `docs/STUDENT_QUICKSTART.md` hướng dẫn học sinh kết nối Wi-Fi, quét mã QR, theo dõi trạng thái lưu bài và chính sách hỗ trợ thi giấy.
  - `EG-711`: **REVIEW** — Tài liệu hướng dẫn khảo sát và thu thập phản hồi của 1–2 giáo viên đã sẵn sàng trong runbook; giữ trạng thái `REVIEW` trung thực chờ tiến hành trên lớp học thật.
  - `EG-712`: **DONE** — Soạn thảo `docs/RELEASE_CHECKLIST.md` kiểm kê chi tiết 59 thư viện Python (100% không AGPL) và các gói frontend, rà soát an toàn PII, công bằng chống gian lận và xác lập nhãn **Beta** đúng quy định.

---

## 5.2. Chức năng đã triển khai

### Backend
- **Đóng gói PyInstaller onedir:** Cấu hình `desktop/examguard.spec` gom toàn bộ mã nguồn backend, Alembic migrations, bộ font TrueType offline (`DejaVuSans.ttf`, `Ubuntu-R.ttf`), và thư mục frontend static build `frontend/dist/`.
- **Cơ chế xác định đường dẫn động (`BundlePaths`):** Hàm `resolve_bundle_paths()` trong `desktop/launcher.py` tự động phát hiện cờ `sys.frozen` để trỏ tài nguyên vào `sys._MEIPASS` và đặt thư mục dữ liệu thi `ExamGuardData` ngay cạnh tệp `ExamGuard.exe`.
- **Bảo vệ sao lưu đĩa đầy nguyên tử (`Atomic Backup Staging`):** Sửa đổi `backend/app/services/backup_service.py` tạo tệp tạm `.zip.tmp` trước khi đổi tên thay thế; bắt ngoại lệ `OSError` / `sqlite3.Error` để xóa sạch tệp rác và trả về lỗi `HTTP 507 Insufficient Storage`, bảo vệ CSDL thi gốc không bị suy suyển.
- **Xử lý chuẩn mã hóa Console Windows:** Bổ sung cơ chế `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` ngăn chặn triệt để lỗi `UnicodeEncodeError / charmap` trên các bản Windows sử dụng trang mã CP1252 khi in thông báo tiếng Việt có dấu ra màn hình dòng lệnh.

### Frontend
- **Phân phối tĩnh tích hợp (`Static Bundle Serving`):** Giao diện React SPA được nhúng trực tiếp vào bản phân phối `ExamGuard.exe`, phục vụ tại route gốc `/` và `/join` với tiêu đề và tài nguyên hoàn toàn cục bộ.
- **Kiểm toán Zero-CDN:** 100% phông chữ (`Be Vietnam Pro`, `JetBrains Mono`), công thức toán học (`KaTeX`), và biểu tượng (`lucide-react`) được nạp từ các tệp `.woff2` / `.ttf` nội bộ trong gói phát hành.

### APIs
- Hỗ trợ đầy đủ cờ dòng lệnh trong Launcher:
  - `--version`: Hiển thị phiên bản `ExamGuard 0.1.0-beta.1` và thoát ngay với mã 0.
  - `--no-browser`: Tắt tính năng tự động mở trình duyệt (dành cho chế độ chạy kiểm thử tải / nền).
  - `--host`: Cho phép chỉ định địa chỉ lắng nghe (`0.0.0.0` hoặc `127.0.0.1`).
  - `--port`: Cho phép chỉ định cổng ưu tiên với cơ chế fallback tự động sang cổng ngẫu nhiên nếu bị chiếm dụng.
  - `--data-dir`: Cho phép chỉ định thư mục lưu trữ dữ liệu tùy biến.

### Thuật toán & Cơ chế quan trọng
- **Thuật toán sinh bản sao lưu nguyên tử và kiểm tra toàn vẹn:** Sử dụng SQLite Online Backup API (`conn.backup`) chụp snapshot bộ nhớ nhất quán của CSDL đang chạy dưới chế độ WAL; tính toán mã băm SHA-256 cho từng tệp thành phần và lưu vào `manifest.json`.
- **Cơ chế đo tải bất đồng bộ đa luồng ảo:** `tools/load_test.py` kết hợp `asyncio` và `httpx.AsyncClient` điều phối 45 luồng học sinh ảo thực hiện đồng loạt các tác vụ tham gia phòng, lưu đáp án phân tán, gửi nhịp tim, và nộp bài đồng thời trong vòng đời tiến trình Uvicorn thực tế.

---

## 5.3. Danh sách file

### File tạo mới
- [`CHANGELOG.md`](file:///d:/Project/ExamGuard/CHANGELOG.md): Nhật ký các phiên bản và tính năng của bản phát hành `v0.1.0-beta.1`.
- [`desktop/examguard.spec`](file:///d:/Project/ExamGuard/desktop/examguard.spec): Đặc tả PyInstaller onedir cho ứng dụng Windows Portable.
- [`tools/build_portable.ps1`](file:///d:/Project/ExamGuard/tools/build_portable.ps1): Kịch bản tự động hóa build frontend, build PyInstaller EXE, đính kèm hướng dẫn và nén tệp release ZIP kèm SHA-256.
- [`tools/load_test.py`](file:///d:/Project/ExamGuard/tools/load_test.py): Kịch bản benchmark kiểm thử tải dồn dập 45 học sinh ảo đồng thời.
- [`backend/tests/test_p7_resilience_and_recovery.py`](file:///d:/Project/ExamGuard/backend/tests/test_p7_resilience_and_recovery.py): Bộ kiểm thử tự động khả năng phục hồi thảm họa, zero-CDN audit, và di trú dữ liệu đa máy tính.
- [`docs/LAN_AP_GUIDE.md`](file:///d:/Project/ExamGuard/docs/LAN_AP_GUIDE.md): Cẩm nang thiết lập mạng LAN Wi-Fi nội bộ không Internet cho lớp thi.
- [`docs/TEACHER_QUICKSTART.md`](file:///d:/Project/ExamGuard/docs/TEACHER_QUICKSTART.md): Hướng dẫn sử dụng nhanh 5 bước dành cho giáo viên.
- [`docs/STUDENT_QUICKSTART.md`](file:///d:/Project/ExamGuard/docs/STUDENT_QUICKSTART.md): Hướng dẫn tham gia thi trên điện thoại dành cho học sinh.
- [`docs/RELEASE_CHECKLIST.md`](file:///d:/Project/ExamGuard/docs/RELEASE_CHECKLIST.md): Danh mục kiểm tra bản quyền thư viện, an toàn dữ liệu và điều kiện phát hành Beta.
- [`docs/phase-reports/PHASE_P7_REPORT.md`](file:///d:/Project/ExamGuard/docs/phase-reports/PHASE_P7_REPORT.md): Báo cáo nghiệm thu kỹ thuật Phase P7 này.

### File chỉnh sửa
- [`.gitignore`](file:///d:/Project/ExamGuard/.gitignore): Ngoại lệ cho phép lưu trữ `!desktop/examguard.spec` vào kho mã nguồn trong khi vẫn bỏ qua các thư mục sinh mã tạm `build/`, `dist/`.
- [`backend/pyproject.toml`](file:///d:/Project/ExamGuard/backend/pyproject.toml): Bổ sung `pyinstaller>=6.10.0` vào nhóm `[project.optional-dependencies] dev`.
- [`backend/requirements.lock.txt`](file:///d:/Project/ExamGuard/backend/requirements.lock.txt): Chuẩn hóa bảng mã ký tự sang UTF-8 và chốt phiên bản `pyinstaller==6.22.3` cùng các phụ thuộc liên quan.
- [`backend/app/core/config.py`](file:///d:/Project/ExamGuard/backend/app/core/config.py): Thêm logic nhận diện `sys.frozen` để đặt thư mục dữ liệu cạnh EXE, bổ sung bắt lỗi `PermissionError` khi khởi tạo thư mục.
- [`backend/app/main.py`](file:///d:/Project/ExamGuard/backend/app/main.py): Ưu tiên tìm thư mục tĩnh `frontend/dist` trong `sys._MEIPASS` khi chạy dạng đóng gói.
- [`backend/alembic/env.py`](file:///d:/Project/ExamGuard/backend/alembic/env.py): Kiểm tra tệp `alembic.ini` tồn tại trước khi cấu hình logging để tương thích chế độ đóng gói.
- [`backend/app/services/backup_service.py`](file:///d:/Project/ExamGuard/backend/app/services/backup_service.py): Xử lý tệp tạm nguyên tử và phản hồi `HTTP 507` khi đầy bộ nhớ đĩa.
- [`desktop/launcher.py`](file:///d:/Project/ExamGuard/desktop/launcher.py): Nâng cấp toàn diện hỗ trợ `--version`, `--host`, UTF-8 console stream, và phân giải đường dẫn tài nguyên `_MEIPASS`.

---

## 5.4. Kiểm thử

### Các bài test đã chạy
1. **Kiểm tra cú pháp & chất lượng mã nguồn:**
   - `ruff check backend/app backend/tests desktop tools`: **0 lỗi** (PASS).
   - `mypy --config-file backend/pyproject.toml backend/app`: **0 lỗi / 41 files checked** (PASS).
   - `mypy --config-file backend/pyproject.toml --explicit-package-bases desktop/launcher.py tools/load_test.py`: **0 lỗi / 2 files checked** (PASS).
2. **Kiểm thử tự động Backend (Pytest):**
   - Lệnh thực thi: `python -m pytest -v` (toàn bộ P0 đến P7).
   - Kết quả: **33/33 tests PASS** trong 10.45s.
   - Các ca kiểm thử P7 mới:
     - `test_offline_zero_cdn_and_static_bundle_audit`: PASS (quét sạch tệp build frontend, không phát hiện tham chiếu CDN ngoài).
     - `test_permission_denied_and_disk_full_during_backup_preserve_db`: PASS (xác minh trả `HTTP 507`, dọn sạch tệp tạm, SQLite DB nguyên vẹn).
     - `test_mid_exam_crash_restart_wal_recovery_and_cross_pc_restore`: PASS (khởi động lại sau crash bảo toàn đáp án đã ACK; khôi phục sang máy tính thứ hai giữ nguyên toàn bộ điểm, đề, ảnh, scan OMR và chuỗi audit).
     - `test_launcher_frozen_path_resolution_and_cli_version`: PASS (kiểm tra phân giải đường dẫn đóng gói `_MEIPASS` và tham số `--version`).
3. **Kiểm thử tự động Frontend (Vitest, ESLint, TypeScript):**
   - `npm run lint`: **0 lỗi** (PASS).
   - `npm run typecheck`: **0 lỗi** (`tsc -b --noEmit` PASS).
   - `npm test`: **11/11 tests PASS** trong 2.45s.
   - `npm run build`: Biển dịch hoàn tất trong 2.61s.
4. **Kiểm thử Tải Thực nghiệm Đa luồng (Benchmark 45 Clients):**
   - Lệnh: `python tools/load_test.py --clients 45 --questions 20 --rounds 3` (3 lượt lặp).
   - Kết quả: **100% PASS** (45/45 học sinh nộp bài thành công, 0/135 mất ACK, p95 thời gian lưu đáp án 727.9 ms).
5. **Khởi chạy Lạnh Gói Tệp Thực thi Portable (Cold-boot on Windows 11 Pro):**
   - Lệnh: `Start-Process dist/ExamGuard/ExamGuard.exe ...`
   - Kết quả: Khởi tạo CSDL SQLite WAL thành công, phản hồi `/api/v1/health` đạt `db_ok: true`, phục vụ SPA `/join` không chứa CDN, ghi nhận **0 socket WAN kết nối ra ngoài**.

### Lỗi đã sửa trong quá trình triển khai
- **Lỗi `UnicodeEncodeError` (charmap CP1252) trên Windows console:** Sửa bằng cách cấu hình `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` và đặt `PYTHONIOENCODING=utf-8` trong các tác vụ thực thi dòng lệnh.
- **Lỗi đếm số lượng `BackupManifest` trong kiểm thử khôi phục đa máy tính:** Sửa bằng việc xác nhận các bảng nghiệp vụ thực chất (`submissions`, `paper_versions`, `omr_scan_submissions`) và kiểm chứng việc tạo bản sao lưu mới thành công trên máy tính thứ hai.

### Phần chưa thể kiểm chứng trên môi trường hiện tại
- Thử nghiệm trên máy tính vật lý cài sạch Windows 10 x64 độc lập (`EG-701`).
- Thử nghiệm kết nối đồng thời 40–50 điện thoại vật lý thực tế qua router Wi-Fi ngoài lớp học (`EG-008`, `EG-407`).
- Khảo sát thực tế lấy ý kiến trực tiếp của 1–2 giáo viên THPT và quét thử ảnh chụp camera từ các bản in phiếu OMR thực tế ngoài đời (`EG-711`).

---

## 5.5. Vấn đề và giới hạn

1. **Giới hạn môi trường phần cứng phòng thi:**
   - Việc phát Wi-Fi bằng tính năng Windows Mobile Hotspot trên một số dòng máy tính bị giới hạn phần cứng ở mức tối đa 8 thiết bị hoặc từ chối phát khi không có cổng mạng WAN Internet. Giải pháp kiến trúc bắt buộc là giáo viên sử dụng một bộ định tuyến Router/Access Point Wi-Fi riêng biệt mang theo phòng thi.
2. **Cảnh báo bảo mật SmartScreen của Windows:**
   - Bản dựng Portable hiện tại được phát hành nội bộ thử nghiệm (`Beta`) và chưa được ký số bằng chứng thư số thương mại trả phí (Code Signing Certificate). Do đó, Windows Defender SmartScreen sẽ hiển thị thông báo ứng dụng lạ ở lần chạy đầu tiên; giáo viên cần chọn *"More info -> Run anyway"* như đã hướng dẫn trong tài liệu.
3. **Phạm vi bảo mật lớp mạng LAN:**
   - Giao tiếp giữa trình duyệt điện thoại học sinh và máy chủ cục bộ hoạt động qua giao thức HTTP/WebSocket nội bộ trong mạng Wi-Fi đóng của lớp thi (`ADR-012`). Không được vận hành hệ thống trên các mạng Wi-Fi công cộng mở không có mật khẩu.

---

## 5.6. Kết luận

- **Tiêu chí nghiệm thu cốt lõi P7:** ĐẠT ĐẦY ĐỦ trên cơ sở kiểm thử tự động, đóng gói Portable Windows, đo tải 45 client ảo, kiểm thử phục hồi thảm họa và xuất bản bộ tài liệu vận hành.
- **Trạng thái cuối cùng của Phase P7:** **PASS (với nhãn Beta `v0.1.0-beta.1`)**.
- **Đánh giá toàn diện dự án (P0 đến P7):**
  - Toàn bộ 8 Phase (`P0` đến `P7`) đã hoàn thành lập trình, kết nối đồng bộ cơ sở dữ liệu và vượt qua kiểm thử tự động toàn diện.
  - Các hạng mục phụ thuộc phần cứng bên ngoài (`EG-008`, `EG-407`, `EG-701`, `EG-711`) được phân loại minh bạch ở trạng thái **`REVIEW`** và sẵn sàng cho giai đoạn thử nghiệm thực địa tại các trường THPT.
