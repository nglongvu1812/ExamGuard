# Next Actions

1. Cài bổ sung thư viện giấy phép mở tương thích (`pypdf` BSD, `numpy` BSD) trong `backend/.venv` và cập nhật `backend/pyproject.toml` + `backend/requirements.lock.txt`.
2. Triển khai Phase P6 (`EG-601`..`EG-609`): migration `0007_paper_bridge_and_omr.py`, `paper_service.py` + `omr_service.py` + `api/paper.py`, `pdf_adapter.py` + `xlsx_converter.py`, UI `PaperBridgePage.tsx` & mở rộng upload `.pdf`/`.xlsx` trong `QuestionBankPage.tsx`.
3. Tạo `backend/tests/test_p6_paper_and_converters.py` và chạy `tools/verify.ps1`, xuất `docs/phase-reports/PHASE_P6_REPORT.md`, sau đó tự động chuyển sang P7 (PyInstaller Portable EXE, load test, crash/disk-full test, docs/runbooks).
