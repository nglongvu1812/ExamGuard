"""Generate pristine, standard Excel template files for classrooms and exam banks."""

from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT_DIR = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def create_excel_classroom_roster() -> Path:
    """Create a standard, cleanly formatted Excel roster for 45 Vietnamese THPT students."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Danh_Sach_Lop"
    ws.views.sheetView[0].showGridLines = True

    # Header Row (Row 1 is headers directly, 100% compliant with _locate_columns)
    headers = ["STT", "Mã học sinh", "Họ và tên", "Ngày sinh", "Giới tính", "Lớp", "Ghi chú"]
    
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    alt_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    ws.row_dimensions[1].height = 28
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    surnames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương"]
    mid_names = ["Văn", "Thị", "Hữu", "Đức", "Minh", "Thu", "Ngọc", "Thanh", "Quốc", "Gia", "Thành", "Phương", "Anh", "Đình", "Xuân"]
    given_names = [
        "An", "Bình", "Cường", "Dũng", "Giang", "Hải", "Khánh", "Linh", "Minh", "Nam",
        "Phúc", "Quân", "Sơn", "Tâm", "Uyên", "Việt", "Xuân", "Yến", "Bảo", "Chi",
        "Đạt", "Hà", "Hưng", "Hương", "Khoa", "Kiên", "Lâm", "Long", "Mai", "Nga",
        "Nghĩa", "Phong", "Phú", "Quyên", "Sang", "Thắng", "Thảo", "Thịnh", "Trang", "Trọng",
        "Trúc", "Tú", "Tùng", "Vinh", "Ý"
    ]

    for i in range(1, 46):
        row_idx = i + 1
        ws.row_dimensions[row_idx].height = 22
        sn = surnames[(i - 1) % len(surnames)]
        mn = mid_names[(i * 3) % len(mid_names)]
        gn = given_names[(i - 1) % len(given_names)]
        full_name = f"{sn} {mn} {gn}"
        gender = "Nữ" if mn in ("Thị", "Thu", "Ngọc", "Phương") or gn in ("Linh", "Uyên", "Yến", "Chi", "Hương", "Mai", "Nga", "Quyên", "Thảo", "Trang", "Trúc", "Ý") else "Nam"
        day = (i % 28) + 1
        month = (i % 12) + 1
        dob = f"{day:02d}/{month:02d}/2008"
        note = "Đội tuyển HSG" if i in (1, 15) else ""

        row_data = [i, f"HS{i:03d}", full_name, dob, gender, "12A1", note]
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.border = thin_border
            if i % 2 == 0:
                cell.fill = alt_fill

            if col_idx in (1, 2, 4, 5, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    widths = [8, 16, 26, 16, 14, 12, 18]
    for idx, w in enumerate(widths, start=1):
        col_letter = get_column_letter(idx)
        ws.column_dimensions[col_letter].width = w

    target = SAMPLES_DIR / "lop_hoc_mau_12A1.xlsx"
    wb.save(target)
    return target


def create_excel_exam_bank() -> Path:
    """Create a comprehensive, 40-question standard Exam Bank Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "De_Thi_Trac_Nghiem"
    ws.views.sheetView[0].showGridLines = True

    headers = ["STT", "Câu hỏi", "A", "B", "C", "D", "Đáp án đúng"]
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    alt_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    ws.row_dimensions[1].height = 28
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    questions = [
        ("Nghiệm của phương trình 2x - 6 = 0 là gì?", "x = 3", "x = -3", "x = 2", "x = 0", "A"),
        ("Đạo hàm của hàm số y = x^4 là gì?", "y' = 4x^3", "y' = x^3", "y' = 4x", "y' = 3x^4", "A"),
        ("Tập xác định của hàm số y = 1/(x - 2) là:", "R \\ {2}", "R", "(2; +vô cùng)", "[2; +vô cùng)", "A"),
        ("Giá trị của cos(0) bằng bao nhiêu?", "1", "0", "-1", "1/2", "A"),
        ("Nguyên hàm của hàm số f(x) = 3x^2 là:", "x^3 + C", "3x^3 + C", "6x + C", "x^2 + C", "A"),
        ("Trong dao động điều hòa, li độ biến thiên điều hòa theo thời gian với chu kỳ T. Gia tốc biến thiên:", "Cùng chu kỳ T nhưng ngược pha với li độ", "Với chu kỳ 2T", "Cùng pha với li độ", "Với chu kỳ T/2", "A"),
        ("Đơn vị đo cường độ điện trường là gì?", "Vôn trên mét (V/m)", "Niutơn (N)", "Vôn (V)", "Ampe (A)", "A"),
        ("Sóng âm có tần số lớn hơn 20.000 Hz được gọi là gì?", "Sóng siêu âm", "Sóng hạ âm", "Âm nghe được", "Tạp âm", "A"),
        ("Công thức định luật Ôm cho đoạn mạch chỉ có điện trở thuần R là:", "I = U / R", "I = U * R", "I = R / U", "I = U^2 / R", "A"),
        ("Hiện tượng giao thoa ánh sáng là bằng chứng thực nghiệm chứng tỏ ánh sáng có:", "Tính chất sóng", "Tính chất hạt", "Vận tốc rất lớn", "Khả năng đâm xuyên mạnh", "A"),
        ("Kim loại nào sau đây dẫn điện tốt nhất ở điều kiện thường?", "Bạc (Ag)", "Đồng (Cu)", "Vàng (Au)", "Nhôm (Al)", "A"),
        ("Chất nào sau đây là chất điện li mạnh trong dung dịch nước?", "NaCl", "CH3COOH", "H2O", "C2H5OH", "A"),
        ("Dung dịch chất nào sau đây làm quỳ tím chuyển sang màu đỏ?", "HCl", "NaOH", "NaCl", "Ba(OH)2", "A"),
        ("Công thức phân tử của khí metan là gì?", "CH4", "C2H4", "C2H2", "C6H6", "A"),
        ("Kim loại kiềm thổ thuộc nhóm nào trong bảng tuần hoàn các nguyên tố hóa học?", "Nhóm IIA", "Nhóm IA", "Nhóm IIIA", "Nhóm VIIA", "A"),
        ("Gen là một đoạn của phân tử ADN mang thông tin mã hóa cho:", "Một chuỗi polipeptit hay một phân tử ARN", "Một phân tử lipid", "Một phân tử đường", "Toàn bộ cấu trúc cơ thể", "A"),
        ("Quá trình phiên mã ở sinh vật nhân thực diễn ra chủ yếu ở đâu?", "Trong nhân tế bào", "Trong tế bào chất", "Tại ribôxôm", "Tại ti thể", "A"),
        ("Thành phần nào sau đây không thuộc cấu trúc của một opêron Lac ở vi khuẩn E. coli?", "Gen điều hòa R", "Vùng vận hành O", "Vùng khởi động P", "Các gen cấu trúc Z, Y, A", "A"),
        ("Cơ thể có kiểu gen AaBb khi giảm phân bình thường tạo ra tối đa bao nhiêu loại giao tử?", "4 loại", "2 loại", "8 loại", "1 loại", "A"),
        ("Đột biến gen là những biến đổi trong cấu trúc của gen liên quan đến:", "Một hoặc một số cặp nuclêôtit", "Toàn bộ nhiễm sắc thể", "Số lượng nhiễm sắc thể", "Hình thái tế bào", "A"),
    ]

    for q_i in range(1, 41):
        row_idx = q_i + 1
        ws.row_dimensions[row_idx].height = 24

        base = questions[(q_i - 1) % len(questions)]
        q_stem = f"Câu {q_i}: {base[0]}"
        correct_letter = ["A", "B", "C", "D"][(q_i - 1) % 4]
        options = [base[1], base[2], base[3], base[4]]

        if correct_letter == "B":
            options[0], options[1] = options[1], options[0]
        elif correct_letter == "C":
            options[0], options[2] = options[2], options[0]
        elif correct_letter == "D":
            options[0], options[3] = options[3], options[0]

        row_vals = [q_i, q_stem, options[0], options[1], options[2], options[3], correct_letter]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.border = thin_border
            if q_i % 2 == 0:
                cell.fill = alt_fill

            if col_idx in (1, 7):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    widths = [8, 55, 32, 32, 32, 32, 16]
    for idx, w in enumerate(widths, start=1):
        col_letter = get_column_letter(idx)
        ws.column_dimensions[col_letter].width = w

    target = SAMPLES_DIR / "de_thi_mau_trac_nghiem_40_cau.xlsx"
    wb.save(target)
    return target


def main() -> int:
    r = create_excel_classroom_roster()
    print("Created:", r.name, f"({r.stat().st_size} bytes)")
    e = create_excel_exam_bank()
    print("Created:", e.name, f"({e.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
