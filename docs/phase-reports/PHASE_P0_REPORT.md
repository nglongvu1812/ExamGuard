# Báo Cáo Hoàn Thành Phase P0 — Repository, Skeleton & Local Runtime

## 1. Tổng quan
- **Tên Phase:** P0 — Foundations (`EG-001`..`EG-008`)
- **Mục tiêu:** Thiết lập nền tảng monorepo, Python 3.12 / FastAPI local server, SQLite WAL + Alembic migration an toàn, React/TypeScript/Tailwind Teacher & Student shell đóng gói 100% offline (zero CDN), Windows launcher và cơ chế dò card mạng LAN + QR động.
- **Danh sách Task:**
  - `EG-001`: Khởi tạo monorepo, lockfile Python & Node, `.gitignore` không lộ secrets — **DONE**
  - `EG-002`: FastAPI `/api/v1/health`, Pydantic Settings, structured rotating log có redact PII/token + tests — **DONE**
  - `EG-003`: SQLite WAL, SQLAlchemy 2, Alembic base migration & DB consistency/backup tests — **DONE**
  - `EG-004`: React Teacher & Student shells, local bundled fonts (`Be Vietnam Pro`, `JetBrains Mono`), `KaTeX`, `Lucide` icons, zero CDN — **DONE**
  - `EG-005`: Windows portable launcher (`desktop/launcher.py`, `run_portable.bat`), port fallback, pre-migrate backup & graceful shutdown — **DONE**
  - `EG-006`: Dynamic LAN interface discovery (`ipconfig` + socket fallback, no hardcoded IP), QR SVG offline & Windows Firewall troubleshooting guide — **DONE**
  - `EG-007`: Local verification script `tools/verify.ps1` (`ruff`, `mypy`, `pytest`, `eslint`, `tsc`, `vitest`, `vite build`) & synthetic sample fixtures — **DONE**
  - `EG-008`: Kiểm thử bundle offline & SPA serving — **REVIEW** (Phần mềm & bundle offline không CDN đã PASS test tự động; kiểm thử thực tế trên 2 điện thoại vật lý qua AP sẽ thực hiện trong đợt pilot phần cứng).

## 2. Chức năng đã triển khai
- **Backend (`backend/app/`):**
  - `core/config.py`: `Settings` (Pydantic v2) quản lý `ExamGuardData` và kiểm tra quyền ghi thực tế trước khi chạy.
  - `core/logging.py`: `RedactingJsonFormatter` ghi file xoay vòng 5MB x 5 bản, tự động ẩn token/Bearer/invite_code/password.
  - `db/session.py`, `db/base.py`, `db/models.py`: SQLite WAL (`PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`), backup SQLite qua `sqlite3.Connection.backup` trước khi migrate Alembic.
  - `launcher/network.py`: Dò card mạng IPv4 nội bộ trên Windows/cross-platform, ưu tiên Wi-Fi/Ethernet, bỏ qua loopback/VM/docker, tạo QR SVG nội bộ không gọi mạng ngoài.
  - `api/health.py`: `GET /api/v1/health` (không PII) và `GET /api/v1/system/network`.
  - `main.py`: FastAPI lifespan + static SPA serving cho `frontend/dist`.
- **Frontend (`frontend/src/`):**
  - `TeacherLayout`, `DashboardPage`, `LanHelpPage`, `PlaceholderSection`, `StudentJoinShell`, `StatusBadge`.
  - Toàn bộ font tiếng Việt (`Be Vietnam Pro`), mono (`JetBrains Mono`), toán (`KaTeX`) và icon (`Lucide`) đóng gói trực tiếp trong `frontend/dist/assets`.
- **Desktop & Tooling:**
  - `desktop/launcher.py`, `desktop/run_portable.bat`, `tools/verify.ps1`, `samples/sample_roster.csv`.

## 3. Danh sách file chính
- Tạo mới: `backend/pyproject.toml`, `backend/requirements.lock.txt`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial_foundation.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/db/base.py`, `backend/app/db/models.py`, `backend/app/db/session.py`, `backend/app/launcher/network.py`, `backend/app/api/health.py`, `backend/app/main.py`, `backend/tests/test_p0_foundation.py`, `desktop/launcher.py`, `desktop/run_portable.bat`, `frontend/*`, `tools/verify.ps1`, `DESIGN.md`, `samples/*`.

## 4. Kiểm thử
- `ruff check backend/app backend/tests`: **PASS** (0 lỗi).
- `mypy --config-file backend/pyproject.toml backend/app`: **PASS** (9 files, 0 lỗi).
- `pytest -v` (backend): **PASS** (6/6 tests: health/no-PII, log redaction, SQLite WAL + Alembic upgrade/downgrade + pre-migrate backup, LAN interface discovery + QR SVG, launcher port fallback + migration, offline SPA + zero external CDN).
- `npm run lint` (`eslint`): **PASS**.
- `npm run typecheck` (`tsc -b --noEmit`): **PASS**.
- `npm test` (`vitest`): **PASS** (2/2 tests: Teacher shell & Student mobile `/join` shell).
- `npm run build` (`vite build`): **PASS** (bundle hoàn chỉnh gồm local fonts/KaTeX).

## 5. Vấn đề và giới hạn
- Chưa test kết nối Wi-Fi thực tế với 2 điện thoại vật lý từ AP rời trong môi trường agent hiện tại (chỉ xác minh qua API & HTTP client nội bộ).
- Hướng shell Desktop chọn mặc định trình duyệt cục bộ tại `127.0.0.1:<port>` (ADR-010) để tránh yêu cầu cài đặt WebView2 trên Windows cũ; có thể bổ sung wrapper tùy chọn ở P7 nếu cần.

## 6. Kết luận
- **Trạng thái cuối cùng:** **PASS** (đạt đầy đủ tiêu chí nền tảng phần mềm P0; mục test 2 điện thoại vật lý được ghi nhận `REVIEW` cho pilot phần cứng).
- **Chuyển tiếp tự động:** Chuyển sang **Phase P1 — Classrooms & Roster Identity (`EG-101`..`EG-107`)**.
