# Technical Decisions

- Tham chiếu chính thức: `DECISIONS.md` (ADR-001 đến ADR-012).
- **ADR-010 (Đánh giá tại P0):**
  - Backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite WAL, Alembic, Uvicorn.
  - Frontend: React 19/18, TypeScript strict, Vite, Tailwind CSS, Lucide Icons (bundled), Font nội bộ (`@fontsource/be-vietnam-pro` / `@fontsource/jetbrains-mono`), KaTeX cục bộ (`katex`).
  - Desktop Launcher: Python launcher khởi chạy Uvicorn + mở trình duyệt mặc định tại `http://127.0.0.1:<port>` (browser-based teacher shell mặc định để tránh phụ thuộc WebView2 nặng trên máy Windows cũ, có cấu hình mở rộng pywebview nếu cần).
