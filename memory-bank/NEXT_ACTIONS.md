# Next Actions

1. Kiểm tra `reportlab` và Pillow trong `backend/.venv`, chuẩn bị font TTF hỗ trợ tiếng Việt (copy offline vào `backend/app/assets/fonts/`).
2. Triển khai Phase P5 (`EG-501`..`EG-510`): migration `0006_grading_and_receipts.py`, pure scoring engine, regrade versioning (`GradeRun`, `ScoreVersion`, `ReceiptVersion`), review/publish strict gate, Excel export (chống formula injection), PDF/PNG receipt, phúc khảo UI (`T7`, `T8`) và kết quả học sinh (`S7`), negative security tests.
3. Tiếp tục P6 (Paper bridge + OMR + PDF/XLSX import) và P7 (PyInstaller Portable Windows build + load test + quickstart/checklist).
