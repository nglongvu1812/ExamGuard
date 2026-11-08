# Active Context — Agent cập nhật sau mọi phiên

## Current focus

- Phase: P6 — Paper Bridge & Extended Converter (`EG-601`..`EG-609`).
- Objective: Triển khai sinh nhiều mã đề giấy định danh rõ (tái sử dụng hoán vị xác định `option_id`), xuất PDF A4 đề in + đáp án offline, sinh phiếu OMR có ô đánh dấu 4 góc + SBD/Mã đề/câu hỏi, xử lý ảnh chụp/scan OMR (crop, deskew nhẹ, đo mật độ tô & độ tin cậy), giao diện giáo viên duyệt bài OMR mơ hồ & lưu ảnh gốc bất biến, đưa điểm thi giấy vào lịch sử chấm chung, mở rộng converter hỗ trợ `.pdf` (cột/hình ảnh/vector crop) và `.xlsx` teacher profile kèm báo cáo benchmark + đánh giá OCR cục bộ.

## Last completed work

- 2026-11-08: Hoàn thành Phase P5 (`EG-501`..`EG-510` DONE). `tools/verify.ps1` PASS (26/26 pytest, 10/10 vitest, ruff, mypy, eslint, tsc, vite build). Báo cáo tại `docs/phase-reports/PHASE_P5_REPORT.md`.
