# Active Task

- **Phase hiện tại:** P6 — Đề giấy, Chấm OMR & Converter mở rộng (`EG-601`..`EG-609`)
- **Task kế tiếp:** `EG-601`..`EG-609` (Migration `0007_paper_bridge_and_omr.py`, `PaperPacket`/`OmrScanSubmission`, sinh mã đề giấy & phiếu OMR A4 ReportLab, pipeline crop/deskew/đo độ tô OMR + review UI + bridge vào `Submission`/`ScoreVersion`, converter `.pdf`/`.xlsx`, benchmark + báo cáo OCR cục bộ).
- **Lệnh kiểm chứng chuẩn:** `powershell -ExecutionPolicy Bypass -File tools\verify.ps1`
