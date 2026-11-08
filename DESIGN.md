# Design System — ExamGuard

## Mode & Visual World
- **Primary Mode:** Operate (Desktop Teacher Console + Distraction-Free Mobile Student Exam Surface).
- **Aesthetic Direction:** Clean Academic & Reliable Precision — lấy cảm hứng từ tài liệu thi chuẩn mực trên nền giấy trắng dịu mắt, bảng điều khiển rõ ràng, ưu tiên tối đa khả năng đọc tiếng Việt có dấu, công thức toán học và trạng thái lưu bài minh bạch.
- **Light Mode Mandatory:** Phù hợp ánh sáng phòng học ban ngày và phòng máy trường học; giảm chói, tương phản đạt chuẩn WCAG AA (≥4.5:1 cho văn bản chính).

## Typography (100% Self-Hosted Offline)
- **UI & Body Sans:** `Be Vietnam Pro` (bundled via `@fontsource/be-vietnam-pro`: 400, 500, 600, 700) — thiết kế chuyên biệt cho dấu tiếng Việt rõ ràng, cân đối.
- **Data / Codes / Timers:** `JetBrains Mono` (bundled via `@fontsource/jetbrains-mono`: 500, 600) kết hợp `font-variant-numeric: tabular-nums` cho đồng hồ đếm ngược, IP LAN, mã tham gia, mã học sinh.
- **Math Rendering:** `KaTeX` (bundled locally via `katex/dist/katex.min.css` và fonts WOFF2 cục bộ).

## Color Tokens
- **Canvas Background:** `#F8FAFC` (Slate 50 — dịu mắt)
- **Surface / Card / Exam Sheet:** `#FFFFFF` với viền `1px solid #E2E8F0`
- **Primary Brand / Action:** `#1E3A5F` (Academic Navy — điềm tĩnh, nghiêm túc) · Hover `#162C49`
- **Interactive Accent:** `#0F766E` (Teal 700 — cho trạng thái sẵn sàng/tiến độ đang thi)
- **Text Primary:** `#0F172A` (Slate 900)
- **Text Secondary:** `#475569` (Slate 600)
- **Text Muted:** `#64748B` (Slate 500)
- **Semantic Statuses (Luôn đi kèm icon + chữ mô tả, không dùng màu đơn thuần):**
  - `Success / Đã lưu / Đã duyệt`: `#15803D` trên nền `#F0FDF4`, viền `#BBF7D0`
  - `Warning / Cần xác minh / Đang lưu`: `#B45309` trên nền `#FFFBEB`, viền `#FDE68A`
  - `Danger / Mất kết nối / Tạm khóa`: `#B91C1C` trên nền `#FEF2F2`, viền `#FECACA`
  - `Info / Phòng chờ / Đang đồng bộ`: `#0369A1` trên nền `#F0F9FF`, viền `#BAE6FD`

## Layout & Spacing Rules
- **Teacher Console (1280px+):** Sidebar cố định `256px` bên trái (7 mục chính theo `UI_SPEC.md`), vùng nội dung chính tối đa `1280px` padding `24px–32px`. Bảng dữ liệu mật độ vừa phải, dễ quét hàng ngang.
- **Student Mobile Exam (360px–430px):** Single-column distraction-free. Sticky header gọn (`56px`) chứa đồng hồ server + badge trạng thái lưu (`Đã lưu` / `Đang lưu...` / `Mất kết nối`). Vùng câu hỏi `65ch` max-width, nút đáp án A/B/C/D cao tối thiểu `48px` (touch target ≥44px), khoảng cách tối thiểu `10px`. Không cuộn ngang toàn trang; công thức dài hoặc bảng tự cuộn ngang trong vùng chứa nội dung câu hỏi.
- **Focus & Browser Surfaces:** Focus ring `2px solid #0F766E` offset `2px`. Selection nền `#DBEAFE` chữ `#0F172A`. Custom scrollbar mảnh trung tính.
