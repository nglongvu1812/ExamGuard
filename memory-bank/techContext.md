# Technical Context — kiểm chứng khi P0

Proposed backend: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite WAL, Alembic, HTTPX, pytest.

Proposed frontend: TypeScript strict, React, Vite, Tailwind, WebSocket + REST, Playwright/Vitest, local assets/KaTeX.

Proposed document pipeline: OOXML/lxml/python-docx, OMML/MathML transform, PyMuPDF PDF blocks/crop (license review), OpenCV OMR P2, openpyxl, reportlab/alternative.

Proposed packaging: PyInstaller onedir first; desktop teacher shell decide pywebview vs browser in P0, Windows 10/11 x64. No cloud resource required in exam runtime.

Environments and exact versions **NOT YET VERIFIED**. Agent must inspect before freezing dependency versions and document compatibility tests. Project must run development tests on available OS and separate packaged validation on real Windows.

Network: one laptop host, 2.4/5 GHz AP as tested; dynamic IP QR; HTTP in trusted LAN baseline with security caveat; HTTPS local provisioning to research before production security claims. No fixed `192.168.137.1` assumption.
