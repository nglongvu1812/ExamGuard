"""Build comprehensive, beautifully formatted sample classroom rosters and exam files in samples/."""

from __future__ import annotations

import io
import struct
import sys
import zlib
from pathlib import Path

import openpyxl
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.shared import Inches, Pt, RGBColor
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SAMPLES_DIR = ROOT_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 1. CLASSROOM ROSTER SAMPLES
# ==============================================================================

def create_rich_roster_xlsx() -> Path:
    """Create a professionally styled 45-student roster Excel matching Vietnamese school standards."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Danh sách Lớp 12A1"
    ws.views.sheetView[0].showGridLines = True

    # Title Banner
    ws.merge_cells("A1:G1")
    title_cell = ws["A1"]
    title_cell.value = "DANH SÁCH HỌC SINH THAM GIA KIỂM TRA NĂM HỌC 2026 - 2027"
    title_cell.font = Font(name="Arial", size=14, bold=True, color="1B365D")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    # Subtitle
    ws.merge_cells("A2:G2")
    sub_cell = ws["A2"]
    sub_cell.value = "Lớp: 12A1 — Trường THPT Chu Văn An — Giáo viên chủ nhiệm: Thầy Hoàng Minh Tuấn"
    sub_cell.font = Font(name="Arial", size=10, italic=True, color="555555")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # Headers
    headers = ["STT", "Mã học sinh", "Họ và tên", "Ngày sinh", "Giới tính", "Lớp", "Ghi chú"]
    ws.row_dimensions[4].height = 26
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Student Names Data (45 authentic Vietnamese students)
    surnames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương"]
    mid_names = ["Văn", "Thị", "Hữu", "Đức", "Minh", "Thu", "Ngọc", "Thanh", "Quốc", "Gia", "Thành", "Phương", "Anh", "Đình", "Xuân"]
    given_names = ["An", "Bình", "Cường", "Dũng", "Giang", "Hải", "Khánh", "Linh", "Minh", "Nam",
                   "Phúc", "Quân", "Sơn", "Tâm", "Uyên", "Việt", "Xuân", "Yến", "Bảo", "Chi",
                   "Đạt", "Hà", "Hưng", "Hương", "Khoa", "Kiên", "Lâm", "Long", "Mai", "Nga",
                   "Nghĩa", "Phong", "Phú", "Quyên", "Sang", "Thắng", "Thảo", "Thịnh", "Trang", "Trọng",
                   "Trúc", "Tú", "Tùng", "Vinh", "Ý"]

    alt_fill = PatternFill(start_color="F2F6FA", end_color="F2F6FA", fill_type="solid")

    for i in range(1, 46):
        row_idx = 4 + i
        ws.row_dimensions[row_idx].height = 20
        sn = surnames[(i - 1) % len(surnames)]
        mn = mid_names[(i * 3) % len(mid_names)]
        gn = given_names[(i - 1) % len(given_names)]
        full_name = f"{sn} {mn} {gn}"
        gender = "Nữ" if mn in ("Thị", "Thu", "Ngọc", "Phương") or gn in ("Linh", "Uyên", "Yến", "Chi", "Hương", "Mai", "Nga", "Quyên", "Thảo", "Trang", "Trúc", "Ý") else "Nam"
        day = (i % 28) + 1
        month = (i % 12) + 1
        dob = f"{day:02d}/{month:02d}/2008"
        note = "Đội tuyển Toán" if i in (1, 15) else ("Đội tuyển Lý" if i in (5, 20) else "")

        row_data = [i, f"HS{i:03d}", full_name, dob, gender, "12A1", note]
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.border = thin_border
            if i % 2 == 0:
                cell.fill = alt_fill
            # Alignments
            if col_idx in (1, 2, 4, 5, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # Column widths
    col_widths = [8, 16, 26, 16, 14, 12, 18]
    for idx, w in enumerate(col_widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = w

    target = SAMPLES_DIR / "mau_danh_sach_lop_12A1_chuan.xlsx"
    wb.save(target)
    return target


def create_simple_roster_csv() -> Path:
    """Create a simple lightweight CSV roster for quick testing."""
    target = SAMPLES_DIR / "mau_danh_sach_lop_10A2_co_ban.csv"
    lines = [
        "STT,Mã học sinh,Họ và tên,Lớp,Ghi chú",
        "1,HS101,Nguyễn Gia Bảo,10A2,Lớp trưởng",
        "2,HS102,Trần Thị Mai Chi,10A2,Bí thư",
        "3,HS103,Lê Hoàng Dũng,10A2,",
        "4,HS104,Phạm Thu Giang,10A2,",
        "5,HS105,Hoàng Đức Hải,10A2,",
        "6,HS106,Vũ Ngọc Khánh,10A2,",
        "7,HS107,Đặng Thùy Linh,10A2,",
        "8,HS108,Bùi Quang Minh,10A2,",
        "9,HS109,Đỗ Phương Nam,10A2,",
        "10,HS110,Hồ Cẩm Tú,10A2,",
    ]
    target.write_text("\n".join(lines), encoding="utf-8-sig")
    return target


# ==============================================================================
# 2. SAMPLE EXAM: TOÁN 12 (DOCX WITH FORMULAS, DIAGRAMS & TABLES)
# ==============================================================================

def _make_graph_diagram_png() -> bytes:
    """Generate a clean 2D function graph PNG image for math questions."""
    img = Image.new("RGB", (320, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Grid lines
    for x in range(20, 310, 30):
        draw.line([(x, 10), (x, 190)], fill=(240, 240, 240), width=1)
    for y in range(10, 195, 30):
        draw.line([(10, y), (310, y)], fill=(240, 240, 240), width=1)

    # Coordinate axes
    draw.line([(20, 100), (300, 100)], fill=(60, 60, 60), width=2)   # Ox
    draw.polygon([(300, 97), (308, 100), (300, 103)], fill=(60, 60, 60))
    draw.line([(160, 190), (160, 15)], fill=(60, 60, 60), width=2)   # Oy
    draw.polygon([(157, 15), (160, 7), (163, 15)], fill=(60, 60, 60))

    # Cubic curve y = x^3 - 3x
    points: list[tuple[int, int]] = []
    for px in range(70, 250):
        x_val = (px - 160) / 40.0
        y_val = -(x_val**3 - 3 * x_val) * 25.0 + 100.0
        points.append((px, int(max(15, min(185, y_val)))))
    draw.line(points, fill=(31, 78, 121), width=3)

    # Labels
    draw.text((165, 102), "O", fill=(40, 40, 40))
    draw.text((295, 108), "x", fill=(40, 40, 40))
    draw.text((145, 12), "y", fill=(40, 40, 40))
    draw.text((120, 30), "y = f(x)", fill=(31, 78, 121))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_math_exam_docx() -> Path:
    """Create a high-school Math exam DOCX with OMML formulas, table, chart and answer keys."""
    doc = Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Header Banner Table (2 columns)
    hdr_table = doc.add_table(rows=1, cols=2)
    hdr_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_table.autofit = False

    cell_left = hdr_table.cell(0, 0)
    p_l = cell_left.paragraphs[0]
    p_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_l1 = p_l.add_run("SỞ GIÁO DỤC VÀ ĐÀO TẠO HÀ NỘI\n")
    r_l1.font.size = Pt(10)
    r_l1.font.bold = True
    r_l2 = p_l.add_run("TRƯỜNG THPT CHU VĂN AN\n")
    r_l2.font.size = Pt(11)
    r_l2.font.bold = True
    r_l3 = p_l.add_run("ĐỀ THI CHÍNH THỨC\n(Đề gồm có 04 trang)")
    r_l3.font.size = Pt(9.5)
    r_l3.font.italic = True

    cell_right = hdr_table.cell(0, 1)
    p_r = cell_right.paragraphs[0]
    p_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_r1 = p_r.add_run("KỲ KIỂM TRA ĐỊNH KỲ NĂM HỌC 2026 - 2027\n")
    r_r1.font.size = Pt(10)
    r_r1.font.bold = True
    r_r2 = p_r.add_run("BÀI THI MÔN: TOÁN HỌC 12\n")
    r_r2.font.size = Pt(11)
    r_r2.font.bold = True
    r_r2.font.color.rgb = RGBColor(31, 78, 121)
    r_r3 = p_r.add_run("Thời gian làm bài: 50 phút (không kể thời gian phát đề)\nMÃ ĐỀ THI: 101")
    r_r3.font.size = Pt(9.5)
    r_r3.font.italic = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Student info block
    p_info = doc.add_paragraph("Họ và tên thí sinh: .............................................................  Số báo danh: .............................")
    p_info.runs[0].font.italic = True
    p_info.runs[0].font.size = Pt(10)
    doc.add_paragraph("―" * 55).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Questions Definition
    diagram_png_path = SAMPLES_DIR / "_temp_math_diagram.png"
    diagram_png_path.write_bytes(_make_graph_diagram_png())

    omml_frac = (
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:f><m:num><m:r><m:t>2x - 1</m:t></m:r></m:num><m:den><m:r><m:t>x + 2</m:t></m:r></m:den></m:f>'
        '</m:oMath>'
    )
    omml_integral = (
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:nary><m:naryPr><m:chr m:val="∫"/><m:limLoc m:val="subSup"/></m:naryPr>'
        '<m:sub><m:r><m:t>0</m:t></m:r></m:sub><m:sup><m:r><m:t>1</m:t></m:r></m:sup>'
        '<m:e><m:r><m:t>e^(2x) dx</m:t></m:r></m:e></m:nary>'
        '</m:oMath>'
    )
    omml_sqrt = (
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:rad><m:radPr/><m:e><m:r><m:t>x^2 - 4x + 5</m:t></m:r></m:e></m:rad>'
        '</m:oMath>'
    )

    math_questions = [
        # 1: Graph diagram question
        ("Cho hàm số y = f(x) liên tục trên R và có đồ thị như hình vẽ bên. Điểm cực đại của đồ thị hàm số đã cho là:",
         diagram_png_path,
         [("A", "(-1; 2)"), ("B", "(1; -2)"), ("C", "(0; 0)"), ("D", "(2; 0)")]),
        # 2: OMML fraction
        ("Đồ thị hàm số y = [OMML_FRAC] có đường tiệm cận đứng là đường thẳng nào sau đây?",
         omml_frac,
         [("A", "x = -2"), ("B", "x = 2"), ("C", "y = 2"), ("D", "y = -1")]),
        # 3: Normal function
        ("Nghiệm của phương trình log_2(x - 1) = 3 là:",
         None,
         [("A", "x = 9"), ("B", "x = 7"), ("C", "x = 8"), ("D", "x = 10")]),
        # 4: OMML Integral
        ("Giá trị của tích phân I = [OMML_INT] bằng bao nhiêu?",
         omml_integral,
         [("A", "(e^2 - 1)/2"), ("B", "e^2 - 1"), ("C", "(e^2 + 1)/2"), ("D", "2(e^2 - 1)")]),
        # 5: Geometry
        ("Thể tích khối lăng trụ có diện tích đáy B = 6 và chiều cao h = 4 bằng:",
         None,
         [("A", "24"), ("B", "8"), ("C", "12"), ("D", "72")]),
        # 6: OMML Sqrt
        ("Tập giá trị nhỏ nhất của hàm số y = [OMML_SQRT] trên tập R là:",
         omml_sqrt,
         [("A", "1"), ("B", "0"), ("C", "5"), ("D", "2")]),
        # 7: Complex numbers
        ("Số phức liên hợp của số phức z = 3 - 4i là:",
         None,
         [("A", "z_bar = 3 + 4i"), ("B", "z_bar = -3 + 4i"), ("C", "z_bar = -3 - 4i"), ("D", "z_bar = 4 - 3i")]),
        # 8: Geometry in space
        ("Trong không gian Oxyz, cho mặt cầu (S): (x - 1)^2 + (y + 2)^2 + (z - 3)^2 = 16. Bán kính R của (S) bằng:",
         None,
         [("A", "4"), ("B", "16"), ("C", "2"), ("D", "8")]),
        # 9: Statistics Table
        ("Một lớp học có kết quả điểm kiểm tra 15 phút môn Toán được ghi lại trong bảng sau:",
         "TABLE_STAT",
         [("A", "15"), ("B", "12"), ("C", "18"), ("D", "25")]),
        # 10: Probability
        ("Gieo một con súc sắc cân đối và đồng chất một lần. Xác suất để xuất hiện mặt có số chấm là số chẵn bằng:",
         None,
         [("A", "1/2"), ("B", "1/3"), ("C", "1/6"), ("D", "2/3")]),
    ]

    # Expand to 20 realistic questions
    for q_idx in range(11, 21):
        math_questions.append((
            f"Cho cấp số cộng (u_n) có số hạng đầu u_1 = {q_idx} và công sai d = 3. Số hạng thứ hai u_2 bằng:",
            None,
            [("A", f"{q_idx + 3}"), ("B", f"{q_idx - 3}"), ("C", f"{q_idx * 3}"), ("D", f"{q_idx + 6}")]
        ))

    for i, (q_text, special, options) in enumerate(math_questions, start=1):
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(6)
        p_q.paragraph_format.space_after = Pt(2)
        r_lbl = p_q.add_run(f"Câu {i}: ")
        r_lbl.bold = True
        r_lbl.font.color.rgb = RGBColor(31, 78, 121)

        if special == diagram_png_path:
            p_q.add_run(q_text)
            doc.add_picture(str(diagram_png_path), width=Inches(2.5))
        elif special == omml_frac:
            parts = q_text.split("[OMML_FRAC]")
            p_q.add_run(parts[0])
            p_q._p.append(parse_xml(omml_frac))
            p_q.add_run(parts[1])
        elif special == omml_integral:
            parts = q_text.split("[OMML_INT]")
            p_q.add_run(parts[0])
            p_q._p.append(parse_xml(omml_integral))
            p_q.add_run(parts[1])
        elif special == omml_sqrt:
            parts = q_text.split("[OMML_SQRT]")
            p_q.add_run(parts[0])
            p_q._p.append(parse_xml(omml_sqrt))
            p_q.add_run(parts[1])
        elif special == "TABLE_STAT":
            p_q.add_run(q_text)
            st_tbl = doc.add_table(rows=2, cols=4)
            st_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            st_tbl.cell(0, 0).text = "Điểm số"
            st_tbl.cell(0, 1).text = "5 - 6"
            st_tbl.cell(0, 2).text = "7 - 8"
            st_tbl.cell(0, 3).text = "9 - 10"
            st_tbl.cell(1, 0).text = "Số học sinh"
            st_tbl.cell(1, 1).text = "8"
            st_tbl.cell(1, 2).text = "15"
            st_tbl.cell(1, 3).text = "17"
            p_sub = doc.add_paragraph("Số học sinh đạt từ 7 điểm trở lên là:")
            p_sub.paragraph_format.space_before = Pt(2)
        else:
            p_q.add_run(q_text)

        # Options layout (4 inline options on single line)
        opt_line = "      ".join(f"{lbl}. {txt}" for lbl, txt in options)
        p_opt = doc.add_paragraph(opt_line)
        p_opt.paragraph_format.left_indent = Inches(0.25)
        p_opt.paragraph_format.space_after = Pt(4)

    diagram_png_path.unlink(missing_ok=True)

    # Footer Answer Key Table
    doc.add_page_break()
    p_key_hd = doc.add_heading("BẢNG ĐÁP ÁN THAM CHIẾU", level=2)
    p_key_hd.alignment = WD_ALIGN_PARAGRAPH.CENTER

    key_table = doc.add_table(rows=3, cols=11)
    key_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    key_table.cell(0, 0).text = "Câu"
    key_table.cell(1, 0).text = "Đ.Án"
    key_table.cell(2, 0).text = "Câu/ĐA"

    for c in range(1, 11):
        key_table.cell(0, c).text = str(c)
        key_table.cell(1, c).text = "A"

    for c in range(11, 21):
        key_table.cell(2, c - 10).text = f"{c}: A"

    target = SAMPLES_DIR / "mau_de_thi_toan_12_40_cau.docx"
    doc.save(str(target))
    return target


# ==============================================================================
# 3. SAMPLE EXAM: TIẾNG ANH THPT (DOCX WITH READING PASSAGE)
# ==============================================================================

def create_english_exam_docx() -> Path:
    """Create a high-school English test DOCX with reading comprehension and grammar."""
    doc = Document()

    # Header
    p_hd = doc.add_paragraph()
    p_hd.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p_hd.add_run("BỘ ĐỀ KIỂM TRA MẪU TIẾNG ANH LỚP 12 — CHUẨN THPT\n")
    r1.font.bold = True
    r1.font.size = Pt(13)
    r1.font.color.rgb = RGBColor(31, 78, 121)
    r2 = p_hd.add_run("Thời gian làm bài: 45 phút — Gồm 25 câu hỏi trắc nghiệm khách quan")
    r2.font.italic = True
    r2.font.size = Pt(10)

    doc.add_paragraph("―" * 55).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Section 1: Pronunciation
    p_sec1 = doc.add_paragraph("Mark the letter A, B, C, or D to indicate the word whose underlined part differs from the other three:")
    p_sec1.runs[0].font.bold = True

    pron_questions = [
        ("Câu 1: Choose the word with a different sound in the underlined part:", [("A", "cat"), ("B", "hat"), ("C", "car"), ("D", "bat")]),
        ("Câu 2: Choose the word with a different sound in the underlined part:", [("A", "walked"), ("B", "played"), ("C", "cleaned"), ("D", "called")]),
        ("Câu 3: Choose the word with a different main stress:", [("A", "teacher"), ("B", "student"), ("C", "doctor"), ("D", "police")]),
    ]
    for q_text, opts in pron_questions:
        p = doc.add_paragraph(q_text)
        p.runs[0].font.bold = True
        doc.add_paragraph("      ".join(f"{lbl}. {txt}" for lbl, txt in opts))

    # Section 2: Grammar & Vocabulary
    p_sec2 = doc.add_paragraph("Mark the letter A, B, C, or D to indicate the correct answer to each of the following questions:")
    p_sec2.runs[0].font.bold = True

    gram_questions = [
        ("Câu 4: If I ________ enough money, I would buy that new laptop for study.", [("A", "had"), ("B", "have"), ("C", "will have"), ("D", "had had")]),
        ("Câu 5: The Internet ________ in almost every household nowadays.", [("A", "is used"), ("B", "uses"), ("C", "was used"), ("D", "has used")]),
        ("Câu 6: She asked me where I ________ the previous summer holiday.", [("A", "had gone"), ("B", "went"), ("C", "go"), ("D", "have gone")]),
        ("Câu 7: Despite the heavy rain, the students ________ to school on time.", [("A", "went"), ("B", "go"), ("C", "are going"), ("D", "have gone")]),
        ("Câu 8: This is the most interesting book that I have ________ read.", [("A", "ever"), ("B", "never"), ("C", "already"), ("D", "yet")]),
    ]
    for q_text, opts in gram_questions:
        p = doc.add_paragraph(q_text)
        p.runs[0].font.bold = True
        doc.add_paragraph("      ".join(f"{lbl}. {txt}" for lbl, txt in opts))

    # Section 3: Reading Comprehension
    p_sec3 = doc.add_paragraph("Read the following passage and mark the letter A, B, C, or D to indicate the correct answer:")
    p_sec3.runs[0].font.bold = True

    passage = (
        "Education in Vietnam has been undergoing comprehensive modernization. With the rapid expansion of digital "
        "technology, high schools nationwide are adopting blended learning models where local offline tools and interactive "
        "assessments complement classroom teaching. Students learn to develop critical thinking skills and self-directed "
        "learning habits, preparing them effectively for university education and future digital economies."
    )
    p_pass = doc.add_paragraph(passage)
    p_pass.paragraph_format.left_indent = Inches(0.25)
    p_pass.runs[0].font.italic = True

    reading_questions = [
        ("Câu 9: What is the main topic of the passage?", [("A", "Educational modernization in Vietnam"), ("B", "Traditional exams"), ("C", "Computer games"), ("D", "University tuition fees")]),
        ("Câu 10: According to the passage, blended learning models help students to:", [("A", "Develop critical thinking"), ("B", "Avoid homework"), ("C", "Play games in class"), ("D", "Graduate early")]),
    ]
    for q_text, opts in reading_questions:
        p = doc.add_paragraph(q_text)
        p.runs[0].font.bold = True
        doc.add_paragraph("      ".join(f"{lbl}. {txt}" for lbl, txt in opts))

    # Fill remaining questions up to 25
    for i in range(11, 26):
        doc.add_paragraph(f"Câu {i}: Choose the best option to complete the English sentence number {i}:")
        doc.add_paragraph(f"A. Correct answer {i}      B. Distractor option B      C. Distractor option C      D. Distractor option D")

    # Answer Key
    doc.add_page_break()
    doc.add_heading("BẢNG ĐÁP ÁN ĐỀ THI TIẾNG ANH", level=2).alignment = WD_ALIGN_PARAGRAPH.CENTER
    key_tbl = doc.add_table(rows=2, cols=11)
    key_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c in range(11):
        if c == 0:
            key_tbl.cell(0, 0).text = "Câu"
            key_tbl.cell(1, 0).text = "Đáp án"
        else:
            key_tbl.cell(0, c).text = str(c)
            key_tbl.cell(1, c).text = "A"

    target = SAMPLES_DIR / "mau_de_thi_tieng_anh_50_cau.docx"
    doc.save(str(target))
    return target


# ==============================================================================
# 4. SAMPLE EXAM: VẬT LÝ 12 EXCEL QUESTION BANK
# ==============================================================================

def create_physics_exam_xlsx() -> Path:
    """Create a structured 50-question Physics question bank Excel."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Ngân hàng đề Vật lý 12"
    ws.views.sheetView[0].showGridLines = True

    headers = ["STT", "Câu hỏi", "A", "B", "C", "D", "Đáp án đúng"]
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    ws.row_dimensions[1].height = 28
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    physics_topics = [
        ("Một vật dao động điều hòa theo phương trình x = A*cos(omega*t + phi). Đại lượng omega được gọi là gì?",
         "Tần số góc của dao động", "Chu kỳ dao động", "Biên độ dao động", "Pha ban đầu của dao động", "A"),
        ("Con lắc lò xo gồm vật khối lượng m và lò xo độ cứng k dao động điều hòa với chu kỳ T bằng:",
         "T = 2*pi*sqrt(m/k)", "T = 2*pi*sqrt(k/m)", "T = 1/(2*pi)*sqrt(m/k)", "T = 2*pi*sqrt(g/l)", "A"),
        ("Bước sóng lambda là quãng đường mà sóng truyền được trong khoảng thời gian bằng bao nhiêu?",
         "Một chu kỳ sóng", "Một nửa chu kỳ sóng", "Hai chu kỳ sóng", "Một phần tư chu kỳ sóng", "A"),
        ("Đặc trưng sinh lý của âm bao gồm những yếu tố nào sau đây?",
         "Độ cao, độ to và âm sắc", "Tần số, cường độ âm và đồ thị âm", "Tốc độ truyền âm và bước sóng", "Biên độ âm và mức cường độ âm", "A"),
        ("Trong mạch điện xoay chiều chỉ có tụ điện C, cường độ dòng điện tức thời so với điện áp hai đầu tụ điện:",
         "Sớm pha pi/2 so với điện áp", "Trễ pha pi/2 so với điện áp", "Cùng pha với điện áp", "Ngược pha với điện áp", "A"),
        ("Hiện tượng cộng hưởng điện trong đoạn mạch RLC nối tiếp xảy ra khi nào?",
         "omega*L = 1/(omega*C)", "omega*L > 1/(omega*C)", "omega*L < 1/(omega*C)", "R = omega*L", "A"),
        ("Máy biến áp là thiết bị có tác dụng biến đổi đại lượng nào sau đây?",
         "Điện áp xoay chiều mà không làm đổi tần số", "Cả điện áp và tần số dòng điện", "Công suất của dòng điện xoay chiều", "Dòng điện xoay chiều thành một chiều", "A"),
        ("Sóng điện từ là sóng có bản chất là:",
         "Sóng ngang và truyền được trong chân không", "Sóng dọc và truyền được trong chân không", "Sóng ngang và không truyền được trong chân không", "Sóng cơ học lan truyền", "A"),
        ("Tia tử ngoại (UV) có đặc điểm nào sau đây?",
         "Có tác dụng diệt khuẩn và làm phát quang một số chất", "Mắt người nhìn thấy được có màu tím", "Không bị nước và thủy tinh hấp thụ", "Không có tác dụng sinh học", "A"),
        ("Hạt nhân nguyên tử cấu tạo từ các hạt nào?",
         "Proton và nơtron (gọi chung là nuclôn)", "Chỉ gồm các hạt electron", "Proton và electron", "Nơtron và electron", "A"),
    ]

    for i in range(1, 51):
        base = physics_topics[(i - 1) % len(physics_topics)]
        row_idx = i + 1
        ws.row_dimensions[row_idx].height = 22

        q_stem = f"Câu {i}: {base[0]}"
        correct_letter = ["A", "B", "C", "D"][(i - 1) % 4]
        options = [base[1], base[2], base[3], base[4]]

        if correct_letter == "B":
            options[0], options[1] = options[1], options[0]
        elif correct_letter == "C":
            options[0], options[2] = options[2], options[0]
        elif correct_letter == "D":
            options[0], options[3] = options[3], options[0]

        row_vals = [i, q_stem, options[0], options[1], options[2], options[3], correct_letter]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.border = thin_border
            if col_idx in (1, 7):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    widths = [8, 55, 30, 30, 30, 30, 16]
    for idx, w in enumerate(widths, start=1):
        col_letter = openpyxl.utils.get_column_letter(idx)
        ws.column_dimensions[col_letter].width = w

    target = SAMPLES_DIR / "mau_ngan_hang_cau_hoi_vat_ly_50_cau.xlsx"
    wb.save(target)
    return target


# ==============================================================================
# 5. README FOR SAMPLES
# ==============================================================================

def update_samples_readme() -> None:
    readme_content = """# Thư mục Tệp Mẫu Giáo viên & Kiểm tra — ExamGuard

Thư mục này chứa đầy đủ các bộ tệp mẫu giả lập chuẩn hóa theo quy định của Bộ Giáo dục & Đào tạo Việt Nam để giáo viên và hội đồng kiểm thử trải nghiệm ngay lập tức mà không cần tự soạn đề:

---

## 1. Danh sách Lớp học Mẫu (Dùng cho tính năng Quản lý Lớp `/classes`)

| Tên tệp | Định dạng | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`mau_danh_sach_lop_12A1_chuan.xlsx`** | Microsoft Excel (`.xlsx`) | Danh sách 45 học sinh lớp 12A1 đầy đủ cột STT, Mã học sinh (`HS001`..`HS045`), Họ tên tiếng Việt chuẩn có dấu, Ngày sinh, Giới tính, Lớp, Ghi chú. |
| **`mau_danh_sach_lop_10A2_co_ban.csv`** | CSV (`.csv` UTF-8 BOM) | Danh sách 10 học sinh mẫu đơn giản, dùng kiểm tra tính năng nạp nhanh file nhẹ. |

---

## 2. Đề thi & Ngân hàng Câu hỏi Mẫu (Dùng cho tính năng Ngân hàng Đề `/questions`)

| Tên tệp | Định dạng | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`mau_de_thi_toan_12_40_cau.docx`** | Microsoft Word (`.docx`) | Đề thi Toán 12 chuẩn gồm 20 câu tích hợp: công thức toán học OMML (phân số, tích phân, căn thức), bảng số liệu thống kê, ảnh đồ thị hàm số và BẢNG ĐÁP ÁN tham chiếu ở cuối trang để tự động nhận dạng đáp án đúng. |
| **`mau_de_thi_tieng_anh_50_cau.docx`** | Microsoft Word (`.docx`) | Đề thi trắc nghiệm Tiếng Anh THPT gồm 25 câu: Phát âm, Trọng âm, Ngữ pháp, và bài đọc hiểu Reading Comprehension kèm bảng đáp án. |
| **`mau_ngan_hang_cau_hoi_vat_ly_50_cau.xlsx`** | Microsoft Excel (`.xlsx`) | Ngân hàng đề thi môn Vật lý 12 gồm 50 câu hỏi trắc nghiệm khách quan chuẩn cấu trúc cột (`STT`, `Câu hỏi`, `A`, `B`, `C`, `D`, `Đáp án đúng`). |

---

## 3. Phiếu Trắc nghiệm OMR Giấy (Dùng cho tính năng Chấm Giấy `/paper`)

| Tên tệp | Định dạng | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`sample_omr_sheet_filled.png`** | Hình ảnh PNG (A4) | Phiếu trả lời trắc nghiệm chuẩn 4 góc định vị đã được tô sẵn SBD `0007`, mã đề `101` và 40 câu trả lời để kiểm thử tính năng tải ảnh chụp chấm tự động bằng thị giác máy tính. |

---

> **Lưu ý an toàn:** Tất cả họ tên, ngày sinh và số báo danh trong thư mục này đều là **dữ liệu giả lập (synthetic)**, tuân thủ tuyệt đối quy định bảo vệ dữ liệu cá nhân của nhà trường.
"""
    (SAMPLES_DIR / "README.md").write_text(readme_content, encoding="utf-8")


def main() -> int:
    r1 = create_rich_roster_xlsx()
    print("Created:", r1.name, f"({r1.stat().st_size} bytes)")
    r2 = create_simple_roster_csv()
    print("Created:", r2.name, f"({r2.stat().st_size} bytes)")
    m1 = create_math_exam_docx()
    print("Created:", m1.name, f"({m1.stat().st_size} bytes)")
    e1 = create_english_exam_docx()
    print("Created:", e1.name, f"({e1.stat().st_size} bytes)")
    p1 = create_physics_exam_xlsx()
    print("Created:", p1.name, f"({p1.stat().st_size} bytes)")
    update_samples_readme()
    print("Updated: samples/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
