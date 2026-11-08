# Release Checklist — ExamGuard `v0.1.0-beta.1`

Tài liệu rà soát điều kiện kỹ thuật, bản quyền phụ thuộc, an toàn dữ liệu và phạm vi pháp lý trước khi phát hành thử nghiệm (`EG-712`).

---

## 1. Phạm vi & Nhãn phát hành

- **Phiên bản:** `0.1.0-beta.1` (**Classroom Mode — Single Laptop LAN Offline-First**).
- **Lý do gắn nhãn Beta (`MASTER_PLAN.md` & `TASKS.md`):**
  - Đầy đủ kiểm thử tự động (`ruff`, `mypy`, `pytest` P0–P7, `eslint`, `tsc`, `vitest`, `vite build`, load test 45 client ảo, khởi chạy lạnh `ExamGuard.exe` trên Windows 11 x64).
  - Các hạng mục đòi hỏi thiết bị thực địa bên ngoài vẫn giữ trạng thái **`REVIEW`** và chưa tự nhận là hoàn tất pilot:
    - `EG-008`: Kiểm thử kết nối nhiều điện thoại vật lý thực tế qua router AP ngoài.
    - `EG-407`: Ma trận throttle nền trên iOS Safari / Android Chrome ngoài hiện trường.
    - `EG-701`: Chạy thử trên một máy Windows 10 x64 cài sạch riêng biệt (hiện mới kiểm thử EXE trực tiếp trên Microsoft Windows 11 Pro Build 28000).
    - `EG-711`: Khảo sát thử nghiệm trực tiếp với 1–2 giáo viên và ảnh chụp camera thực tế phiếu OMR in giấy.

---

## 2. Kiểm kê Bản quyền Thư viện (Dependency License Audit)

### Backend Runtime (Python 3.12)
| Thành phần | Mục đích | Giấy phép | Đánh giá rủi ro |
| --- | --- | --- | --- |
| `fastapi`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `alembic`, `openpyxl`, `python-docx`, `httptools`, `h11`, `anyio`, `watchfiles` | API server, validation, ORM/migrations, DOCX/XLSX | **MIT** | An toàn (permissive) |
| `uvicorn`, `starlette`, `websockets`, `lxml`, `numpy`, `pypdf`, `reportlab`, `qrcode`, `click`, `httpx`, `python-dotenv`, `MarkupSafe`, `Pygments` | HTTP/WS server, XML/OMML, xử lý OMR, PDF/QR | **BSD-2/3-Clause** (trừ `python-multipart`: **Apache-2.0**, `pillow`: **MIT-CMU**, `certifi`/`pathspec`: **MPL-2.0**) | An toàn (permissive, **0 thư viện AGPL như PyMuPDF**) |
| Font bundled (`DejaVuSans.ttf`, `Ubuntu-R/B.ttf`) | Nhúng offline render PDF/PNG tiếng Việt & Toán | **DejaVu / Ubuntu Font License** | An toàn phân phối offline |
| `pyinstaller` (dev/build tool only) | Đóng gói `ExamGuard.exe` onedir | **GPLv2 w/ Bootloader Exception** | Cho phép phân phối ứng dụng cấp phép không viral |

### Frontend Runtime (`frontend/package.json`)
- `react`, `react-dom`, `react-router-dom`, `katex`, `@fontsource/be-vietnam-pro`, `@fontsource/jetbrains-mono` (**MIT / SIL OFL-1.1**), `lucide-react` (**ISC**). **0 tài nguyên tải từ CDN.**

---

## 3. Rà soát Bảo mật, Công bằng & Quyền riêng tư (`SECURITY_AND_FAIRNESS.md`)

- [x] **Offline 100% (`EG-703`):** Không có thẻ CDN trong `frontend/dist/index.html` / CSS / JS; không gọi cloud/LLM API trong đường chạy thi.
- [x] **Không rò rỉ đáp án sớm:** Học sinh gọi `GET /attempts/me/paper` hoặc WebSocket trước `PUBLISHED` không nhận `correct_option_ids`; test âm tính chặn `403` cho tới khi `CLOSED -> REVIEWED -> PUBLISHED`.
- [x] **Tách biệt quyền & phiên:** Giáo viên dùng local session secret sinh động (`ExamGuardData/server.secret`); học sinh bị khóa cross-attempt `403`, đổi trình duyệt bị chặn trừ khi giáo viên Reset có audit.
- [x] **Lưu vết không sửa ngầm:** Mọi thao tác sửa key, sửa điểm, xử lý sự cố, xác nhận OMR đè/chỉnh đáp án đều bắt buộc `reason >= 3` ký tự và ghi `AuditEvent` liên kết chuỗi `SHA-256`.
- [x] **Khử mã độc đầu vào & xuất:** Chống Zip Bomb / XXE / Path Traversal ở `.docx`/`.pdf`/`.xlsx`/assets; chống CSV/Excel formula injection (`CWE-1236`); che PII trên thẻ chia sẻ PNG (`mask_student_name`, `mask_roster_code`).
- [x] **Không chứa dữ liệu thật / khóa bí mật:** Toàn bộ git history, `samples/` và test fixtures chỉ dùng tên/mã học sinh giả lập (`HS001..`).
- [x] **Không cam kết quá mức:** Giao diện & tài liệu nêu rõ giới hạn HTTP LAN (dùng Wi-Fi lớp riêng) và tín hiệu chuyển tab/rớt mạng không tự chứng minh gian lận.

---

## 4. Rà soát Đóng gói & Chính sách nhà trường

- [x] Gói Portable chạy không cần quyền Administrator (trừ hộp thoại Windows Defender Firewall Private network nếu mở kết nối LAN).
- [x] Tệp nén phát hành `ExamGuard-v0.1.0-beta.1-win64-portable.zip` có tệp checksum `.sha256` đi kèm.
- [ ] **Chữ ký số Authenticode (`Code Signing`):** Chưa ký chứng thư thương mại (cảnh báo SmartScreen trên Windows mới là bình thường ở bản Beta nội bộ; tài liệu `TEACHER_QUICKSTART.md` đã hướng dẫn rõ).
- [ ] **Phê duyệt sử dụng chính thức tại trường:** Việc dùng kết quả vào sổ điểm chính thức thuộc quyền quyết định và quy chế của từng trường THPT / Sở GD&ĐT tại thời điểm triển khai.

---

## 5. Dữ liệu Kiểm chứng Đo đạc Thực tế (Live Measured Evidence)

### 5.1. Bản dựng Portable Windows (`tools/build_portable.ps1`)
- **Tệp phân phối:** `dist/release/ExamGuard-v0.1.0-beta.1-win64-portable.zip`
- **Dung lượng ZIP:** **47.55 MB**
- **Dung lượng thư mục Onedir giải nén:** **92.66 MB**
- **Dung lượng tệp `ExamGuard.exe`:** **17.01 MB**
- **Mã băm SHA-256:** `ebac10dab861ceb7ef09131144fc2a166bf22745b04908b1925bd505246b64b2`
- **Khởi chạy lạnh (Cold-boot smoke check):** Đạt trên Microsoft Windows 11 Pro Build 28000; khởi tạo CSDL WAL và thư mục `ExamGuardData` độc lập không cần quyền Administrator; kiểm tra socket kết nối ghi nhận **0 kết nối ra ngoài Internet**.

### 5.2. Đo tải đồng thời 45 học sinh ảo (`tools/load_test.py` — 3 lượt lặp)
- **Kịch bản:** 45 học sinh tham gia phòng chờ đồng loạt, giáo viên duyệt tất cả & phát đề 20 câu, 3 đợt lưu đáp án xen kẽ heartbeat, nộp bài dồn dập ở cuối, đối chiếu đồng bộ và chấm điểm.
- **Tỉ lệ mất/lệch ACK:** **0/135 (0%)** trên cả 3 lượt chạy.
- **Tỉ lệ nộp bài bền vững vào CSDL:** **45/45 (100%)**.
- **Độ trễ trung bình 3 lượt:**
  - `save_p50`: **186.3 ms**
  - `save_p95`: **727.9 ms** (< 1.0s theo mục tiêu `NFR-03`)
  - `submit_p50`: **99.0 ms**
  - `submit_p95`: **423.5 ms**
- **Đỉnh RAM bộ nhớ máy chủ (Working Set):** **5.21 MB** (tiến trình Uvicorn).
