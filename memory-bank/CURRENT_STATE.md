# Current State

- **Phase vừa hoàn tất:** P5 (`EG-501`..`EG-510` DONE).
- **Phase đang bắt đầu:** P6 — Paper Bridge & Extended Converter (`EG-601`..`EG-609`).
- **Kết quả kiểm thử gần nhất (`tools/verify.ps1`):** PASS (ruff 0 errors, mypy 0 errors / 35 files checked, pytest 26/26, eslint 0 errors, tsc 0 errors, vitest 10/10, vite build 2.59s).
- **Ràng buộc tiếp tục:** Không dùng thư viện AGPL (như PyMuPDF/fitz); dùng `pypdf` (BSD) + `Pillow`/`numpy` (BSD); giữ ảnh scan OMR và file đề gốc bất biến; mọi ca OMR độ tin cậy thấp/tô đúp/thiếu dấu góc phải đưa vào hàng đợi `NEEDS_REVIEW` cho giáo viên xác nhận.
