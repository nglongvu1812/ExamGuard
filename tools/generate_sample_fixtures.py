"""Generate rich synthetic sample fixtures in samples/ for teachers to test out-of-the-box."""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path
from typing import Any

import openpyxl
from docx import Document
from docx.oxml import parse_xml

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

SAMPLES_DIR = ROOT_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def _make_sample_png() -> bytes:
    """Create a 32x32 blue test diagram PNG in memory."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    w, h = 32, 32
    raw_lines = bytearray()
    for y in range(h):
        raw_lines.append(0)  # filter type 0
        for x in range(w):
            # Gradient blue-cyan
            raw_lines.extend((15, int(x * 6), int(y * 6 + 40)))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw_lines))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def generate_roster_xlsx() -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Danh sách lớp"
    ws.append(["STT", "Mã học sinh", "Họ và tên", "Ngày sinh", "Giới tính", "Lớp"])

    first_names = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng"]
    middle_names = ["Văn", "Thị", "Hữu", "Đức", "Minh", "Thu", "Ngọc", "Thanh", "Quốc", "Gia"]
    last_names = ["An", "Bình", "Cường", "Dũng", "Giang", "Hải", "Khánh", "Linh", "Minh", "Nam",
                  "Phúc", "Quân", "Sơn", "Tâm", "Uyên", "Việt", "Xuân", "Yến", "Bảo", "Chi"]

    for i in range(1, 41):
        fn = first_names[(i - 1) % len(first_names)]
        mn = middle_names[(i * 3) % len(middle_names)]
        ln = last_names[(i * 7) % len(last_names)]
        gender = "Nữ" if mn == "Thị" or ln in ("Linh", "Uyên", "Yến", "Chi") else "Nam"
        day = (i % 28) + 1
        month = (i % 12) + 1
        ws.append([
            i,
            f"HS{i:03d}",
            f"{fn} {mn} {ln}",
            f"{day:02d}/{month:02d}/2008",
            gender,
            "12A1",
        ])

    target = SAMPLES_DIR / "sample_roster_40.xlsx"
    wb.save(target)
    return target


def generate_standard_exam_xlsx() -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Đề trắc nghiệm 50 câu"
    ws.append(["STT", "Câu hỏi", "A", "B", "C", "D", "Đáp án đúng"])

    sample_questions = [
        ("Nghiệm của phương trình 2x - 4 = 0 là gì?", "x = 2", "x = -2", "x = 4", "x = 0", "A"),
        ("Đạo hàm của hàm số y = x^3 là gì?", "y' = 3x^2", "y' = x^2", "y' = 3x", "y' = 2x", "A"),
        ("Tập xác định của hàm số y = 1/x là tập nào?", "R \\ {0}", "R", "(0; +vô cùng)", "[-1; 1]", "A"),
        ("Giá trị của sin(pi/2) bằng bao nhiêu?", "1", "0", "-1", "1/2", "A"),
        ("Nguyên hàm của hàm số f(x) = 2x là gì?", "x^2 + C", "2x^2 + C", "x + C", "2 + C", "A"),
        ("Trong dao động điều hòa, vận tốc sớm pha hơn li độ một góc bằng bao nhiêu?", "pi/2 rad", "pi rad", "0 rad", "pi/4 rad", "A"),
        ("Đơn vị của tần số dao động là gì?", "Héc (Hz)", "Jun (J)", "Niu-tơn (N)", "Mét (m)", "A"),
        ("Sóng cơ không truyền được trong môi trường nào?", "Chân không", "Chất rắn", "Chất lỏng", "Chất khí", "A"),
        ("Điện áp hiệu dụng của mạng điện gia đình Việt Nam thông thường là bao nhiêu?", "220 V", "110 V", "380 V", "24 V", "A"),
        ("Hiện tượng quang điện ngoài xảy ra khi ánh sáng kích thích có bước sóng như thế nào?", "Nhỏ hơn hoặc bằng giới hạn quang điện", "Lớn hơn giới hạn quang điện", "Bất kỳ bước sóng nào", "Chỉ trong vùng hồng ngoại", "A"),
    ]

    for i in range(1, 51):
        base = sample_questions[(i - 1) % len(sample_questions)]
        q_text = f"Câu {i}: {base[0]}"
        correct = ["A", "B", "C", "D"][(i - 1) % 4]
        # Rotate options to match correct letter
        opts = [base[1], base[2], base[3], base[4]]
        if correct == "B":
            opts[0], opts[1] = opts[1], opts[0]
        elif correct == "C":
            opts[0], opts[2] = opts[2], opts[0]
        elif correct == "D":
            opts[0], opts[3] = opts[3], opts[0]
        ws.append([i, q_text, opts[0], opts[1], opts[2], opts[3], correct])

    target = SAMPLES_DIR / "sample_exam_standard_50q.xlsx"
    wb.save(target)
    return target


def generate_docx_math_exam() -> Path:
    doc = Document()
    doc.add_heading("ĐỀ KIỂM TRA MẪU TOÁN & VẬT LÝ THPT (20 CÂU)", level=1)
    doc.add_paragraph("Thời gian làm bài: 45 phút — Đề thi gồm 20 câu trắc nghiệm khách quan")

    tmp_png = SAMPLES_DIR / "_temp_chart.png"
    tmp_png.write_bytes(_make_sample_png())

    omml_frac_xml = (
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<m:f><m:num><m:r><m:t>1</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f>"
        "</m:oMath>"
    )

    omml_sqrt_xml = (
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<m:rad><m:radPr/><m:e><m:r><m:t>x^2 + 1</m:t></m:r></m:e></m:rad>"
        "</m:oMath>"
    )

    for i in range(1, 21):
        if i == 1:
            p = doc.add_paragraph(f"Câu {i}: Cho hàm số f(x) có hệ số góc bằng ")
            p._p.append(parse_xml(omml_frac_xml))
            doc.add_paragraph("A. 0.5   B. 1.0   C. 2.0   D. 4.0")
        elif i == 2:
            p = doc.add_paragraph(f"Câu {i}: Tìm tập xác định của biểu thức y = ")
            p._p.append(parse_xml(omml_sqrt_xml))
            doc.add_paragraph("A. R   B. [0; +vô cùng)   C. (-vô cùng; 0]   D. R \\ {0}")
        elif i == 5:
            doc.add_paragraph(f"Câu {i}: Cho đồ thị dao động điều hòa như hình vẽ dưới đây. Chu kỳ dao động T bằng bao nhiêu?")
            doc.add_picture(str(tmp_png), width=docx_shared_inches(1.5))
            doc.add_paragraph("A. 2.0 s   B. 1.0 s   C. 0.5 s   D. 4.0 s")
        elif i == 10:
            doc.add_paragraph(f"Câu {i}: Cho bảng phân bố tần số ghép nhóm sau:")
            tbl = doc.add_table(rows=2, cols=3)
            tbl.cell(0, 0).text = "Khoảng điểm"
            tbl.cell(0, 1).text = "[5; 7)"
            tbl.cell(0, 2).text = "[7; 9)"
            tbl.cell(1, 0).text = "Tần số"
            tbl.cell(1, 1).text = "15"
            tbl.cell(1, 2).text = "25"
            doc.add_paragraph("Số học sinh đạt từ 7 điểm trở lên là:")
            doc.add_paragraph("A. 25   B. 15   C. 40   D. 10")
        else:
            doc.add_paragraph(f"Câu {i}: Khẳng định nào sau đây là đúng về tính chất của hàm số?")
            doc.add_paragraph("A. Hàm số đồng biến khi y' > 0")
            doc.add_paragraph("B. Hàm số nghịch biến khi y' > 0")
            doc.add_paragraph("C. Đạo hàm luôn bằng 0 tại mọi điểm")
            doc.add_paragraph("D. Không xác định được dấu của đạo hàm")

    tmp_png.unlink(missing_ok=True)

    doc.add_heading("BẢNG ĐÁP ÁN", level=2)
    key_tbl = doc.add_table(rows=3, cols=11)
    key_tbl.cell(0, 0).text = "Câu"
    key_tbl.cell(1, 0).text = "Đ.Án"
    key_tbl.cell(2, 0).text = "Câu/Đ.Án"

    # Fill rows 1-10
    for q in range(1, 11):
        key_tbl.cell(0, q).text = str(q)
        key_tbl.cell(1, q).text = "A"

    for q in range(11, 21):
        idx = q - 10
        key_tbl.cell(2, idx).text = f"{q}: A"

    target = SAMPLES_DIR / "sample_exam_math_physics_20q.docx"
    doc.save(str(target))
    return target


def docx_shared_inches(inches: float) -> Any:
    from docx.shared import Inches
    return Inches(inches)


def generate_omr_sheet_png() -> Path:
    from app.services.paper_service import render_omr_template_png

    png_bytes = render_omr_template_png(
        exam_title="Kiểm tra mẫu THPT 2026",
        classroom_name="12A1",
        question_count=40,
        filled_sbd="0007",
        filled_version="101",
        filled_answers={q: [["A", "B", "C", "D"][(q * 3) % 4]] for q in range(1, 41)},
    )
    target = SAMPLES_DIR / "sample_omr_sheet_filled.png"
    target.write_bytes(png_bytes)
    return target


def main() -> int:
    r_path = generate_roster_xlsx()
    print("Generated:", r_path.name, f"({r_path.stat().st_size} bytes)")
    x_path = generate_standard_exam_xlsx()
    print("Generated:", x_path.name, f"({x_path.stat().st_size} bytes)")
    d_path = generate_docx_math_exam()
    print("Generated:", d_path.name, f"({d_path.stat().st_size} bytes)")
    o_path = generate_omr_sheet_png()
    print("Generated:", o_path.name, f"({o_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
