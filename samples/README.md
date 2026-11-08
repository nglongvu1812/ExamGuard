# Thư mục Tệp Mẫu Giáo viên & Kiểm tra — ExamGuard

Thư mục này chứa đầy đủ các bộ tệp mẫu giả lập chuẩn hóa theo quy định của Bộ Giáo dục & Đào tạo Việt Nam để giáo viên và hội đồng kiểm thử trải nghiệm ngay lập tức:

---

## 1. File Lớp học Mẫu bằng Excel (`.xlsx`)

| Tên tệp | Định dạng | Mô tả chi tiết |
| :--- | :--- | :--- |
| **[`lop_hoc_mau_12A1.xlsx`](file:///d:/Project/ExamGuard/samples/lop_hoc_mau_12A1.xlsx)** | Microsoft Excel (`.xlsx`) | **File danh sách lớp 45 học sinh** chuẩn hóa giao diện và cấu trúc: `STT`, `Mã học sinh` (`HS001`..`HS045`), `Họ và tên` (chuẩn tiếng Việt có dấu), `Ngày sinh`, `Giới tính`, `Lớp`, `Ghi chú`. Đã kiểm chứng nạp thành công 45/45 học sinh qua tính năng Quản lý Lớp `/classes`. |
| **`mau_danh_sach_lop_10A2_co_ban.csv`** | CSV (`.csv` UTF-8 BOM) | File CSV đơn giản 10 học sinh dùng để thử nghiệm nạp nhanh. |

---

## 2. File Đề thi Mẫu bằng Excel (`.xlsx`)

| Tên tệp | Định dạng | Mô tả chi tiết |
| :--- | :--- | :--- |
| **[`de_thi_mau_trac_nghiem_40_cau.xlsx`](file:///d:/Project/ExamGuard/samples/de_thi_mau_trac_nghiem_40_cau.xlsx)** | Microsoft Excel (`.xlsx`) | **Ngân hàng đề thi trắc nghiệm 40 câu** chuẩn hóa cấu trúc cột: `STT`, `Câu hỏi`, `A`, `B`, `C`, `D`, `Đáp án đúng`. Bao gồm đầy đủ câu hỏi đa dạng (Toán, Lý, Hóa, Sinh) và đáp án phân bổ đều. Đã kiểm chứng import thành công 40/40 câu vào Ngân hàng Đề `/questions`. |

---

## 3. Các Đề thi Mẫu Bổ sung (Word & OMR)

| Tên tệp | Định dạng | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`mau_de_thi_toan_12_40_cau.docx`** | Microsoft Word (`.docx`) | Đề thi Toán 12 có công thức toán học OMML (phân số, tích phân, căn thức), bảng biểu và ảnh đồ thị hàm số kèm bảng đáp án. |
| **`mau_de_thi_tieng_anh_50_cau.docx`** | Microsoft Word (`.docx`) | Đề thi Tiếng Anh 25 câu: Phát âm, Trọng âm, Ngữ pháp và bài đọc hiểu Reading Comprehension. |
| **`sample_omr_sheet_filled.png`** | Hình ảnh PNG (A4) | Phiếu tô trắc nghiệm A4 đã điền sẵn SBD `0007`, mã đề `101` và 40 câu trả lời để kiểm thử chấm OMR tại `/paper`. |

---

> **Lưu ý an toàn:** Tất cả thông tin học sinh trong thư mục này đều là **dữ liệu giả lập (synthetic)**, tuân thủ tuyệt đối quy định bảo mật và quyền riêng tư trường học.
