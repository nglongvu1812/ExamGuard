"""Classroom & Student Roster CRUD and CSV/XLSX dry-run import service."""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.db.models import ClassMembership, Classroom, Student, TeacherProfile
from app.services.audit_service import record_audit_event
from fastapi import HTTPException, status
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB safety limit

CODE_HEADERS = {"roster_code", "ma_hs", "mã hs", "ma hoc sinh", "mã học sinh", "code", "id"}
NAME_HEADERS = {"full_name", "ho_ten", "họ tên", "họ và tên", "ho va ten", "name", "ten", "tên"}


def ensure_default_teacher(db: Session) -> TeacherProfile:
    teacher = db.execute(select(TeacherProfile).order_by(TeacherProfile.id.asc())).scalar_one_or_none()
    if teacher is None:
        teacher = TeacherProfile(display_name="Giáo viên", settings_json="{}")
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
    return teacher


def create_classroom(
    db: Session,
    *,
    teacher_id: int,
    name: str,
    academic_year: str,
) -> Classroom:
    clean_name = name.strip()
    clean_year = academic_year.strip() or "2026-2027"
    if not clean_name:
        raise HTTPException(status_code=400, detail="Tên lớp học không được để trống.")

    existing = db.execute(
        select(Classroom).where(
            Classroom.teacher_id == teacher_id,
            Classroom.academic_year == clean_year,
            Classroom.name == clean_name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lớp '{clean_name}' năm học {clean_year} đã tồn tại.",
        )

    classroom = Classroom(
        id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        name=clean_name,
        academic_year=clean_year,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


def list_classrooms(
    db: Session,
    *,
    teacher_id: int,
    include_archived: bool = False,
) -> list[tuple[Classroom, int]]:
    stmt = select(Classroom).where(Classroom.teacher_id == teacher_id)
    if not include_archived:
        stmt = stmt.where(Classroom.archived_at.is_(None))
    stmt = stmt.order_by(Classroom.created_at.desc())
    classrooms = db.execute(stmt).scalars().all()

    results: list[tuple[Classroom, int]] = []
    for cls in classrooms:
        count = db.execute(
            select(func.count(ClassMembership.id))
            .join(Student, Student.id == ClassMembership.student_id)
            .where(
                ClassMembership.classroom_id == cls.id,
                ClassMembership.active_to.is_(None),
                Student.archived_at.is_(None),
            )
        ).scalar_one()
        results.append((cls, int(count)))
    return results


def archive_classroom(db: Session, *, classroom_id: str, teacher_id: int) -> Classroom:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None or classroom.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")
    classroom.archived_at = datetime.now(UTC)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="ARCHIVE_CLASSROOM",
        target_type="classroom",
        target_id=classroom.id,
        details={"name": classroom.name},
    )
    db.commit()
    db.refresh(classroom)
    return classroom


def list_classroom_students(
    db: Session,
    *,
    classroom_id: str,
    include_archived: bool = False,
) -> list[Student]:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")
    stmt = (
        select(Student)
        .join(ClassMembership, ClassMembership.student_id == Student.id)
        .where(
            ClassMembership.classroom_id == classroom_id,
            ClassMembership.active_to.is_(None),
        )
    )
    if not include_archived:
        stmt = stmt.where(Student.archived_at.is_(None))
    stmt = stmt.order_by(Student.roster_code.asc())
    return list(db.execute(stmt).scalars().all())


def create_student_in_classroom(
    db: Session,
    *,
    classroom_id: str,
    roster_code: str,
    full_name: str,
    note: str = "",
) -> Student:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")

    clean_code = roster_code.strip().upper()
    clean_name = full_name.strip()
    if not clean_code or not clean_name:
        raise HTTPException(status_code=400, detail="Mã học sinh và họ tên không được để trống.")

    existing = db.execute(
        select(Student).where(Student.roster_code == clean_code)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã học sinh '{clean_code}' đã tồn tại ({existing.full_name}).",
        )

    student = Student(
        id=str(uuid.uuid4()),
        roster_code=clean_code,
        full_name=clean_name,
        metadata_json=json.dumps({"note": note.strip()}, ensure_ascii=False) if note.strip() else "{}",
    )
    db.add(student)
    db.flush()
    db.add(
        ClassMembership(
            classroom_id=classroom_id,
            student_id=student.id,
            active_from=datetime.now(UTC),
        )
    )
    db.commit()
    db.refresh(student)
    return student


def update_student(
    db: Session,
    *,
    student_id: str,
    full_name: str,
    teacher_id: int,
) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh.")
    clean_name = full_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Họ tên học sinh không được để trống.")
    old_name = student.full_name
    student.full_name = clean_name
    student.updated_at = datetime.now(UTC)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="UPDATE_STUDENT_NAME",
        target_type="student",
        target_id=student.id,
        details={"roster_code": student.roster_code, "old_name": old_name, "new_name": clean_name},
    )
    db.commit()
    db.refresh(student)
    return student


def archive_student(db: Session, *, student_id: str, teacher_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh.")
    student.archived_at = datetime.now(UTC)
    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="ARCHIVE_STUDENT",
        target_type="student",
        target_id=student.id,
        details={"roster_code": student.roster_code},
    )
    db.commit()
    db.refresh(student)
    return student


@dataclass(frozen=True)
class ImportPreviewRow:
    row_number: int
    roster_code: str
    full_name: str
    note: str
    status: Literal[
        "NEW",
        "DUPLICATE_IN_FILE",
        "EXISTS_SAME_CLASS",
        "EXISTS_OTHER_CLASS",
        "INVALID",
    ]
    message: str


@dataclass(frozen=True)
class ImportPreviewResult:
    rows: list[ImportPreviewRow]
    new_count: int
    conflict_count: int
    invalid_count: int
    has_conflicts: bool


def _extract_tabular_rows(filename: str, content: bytes) -> list[list[str]]:
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail="Tệp danh sách vượt quá giới hạn 5 MB.")
    if not content:
        raise HTTPException(status_code=400, detail="Tệp danh sách trống.")

    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        decoded: str | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise HTTPException(status_code=400, detail="Không đọc được bảng mã tệp CSV.")
        reader = csv.reader(io.StringIO(decoded))
        return [[str(cell or "").strip() for cell in row] for row in reader]

    if ext == ".xlsx":
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Tệp Excel (.xlsx) bị hỏng hoặc không đúng định dạng.",
            ) from exc
        try:
            sheet = wb.active
            if sheet is None:
                raise HTTPException(status_code=400, detail="Tệp Excel không có sheet dữ liệu.")
            parsed: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                parsed.append([str(cell).strip() if cell is not None else "" for cell in row])
            return parsed
        finally:
            wb.close()

    raise HTTPException(
        status_code=400,
        detail="Định dạng không hỗ trợ. Chỉ chấp nhận tệp .csv hoặc .xlsx.",
    )


def _locate_columns(header_row: list[str]) -> tuple[int, int, int | None]:
    normalized = [col.strip().lower() for col in header_row]
    code_idx: int | None = None
    name_idx: int | None = None
    note_idx: int | None = None

    for idx, col in enumerate(normalized):
        if code_idx is None and (col in CODE_HEADERS or "mã" in col or "code" in col):
            code_idx = idx
        elif name_idx is None and (col in NAME_HEADERS or "tên" in col or "name" in col):
            name_idx = idx
        elif note_idx is None and col in {"note", "ghi chú", "ghi chu"}:
            note_idx = idx

    if code_idx is None or name_idx is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Không tìm thấy cột bắt buộc ('Mã học sinh' / 'roster_code' và 'Họ và tên' / 'full_name'). "
                "Vui lòng kiểm tra dòng tiêu đề."
            ),
        )
    return code_idx, name_idx, note_idx


def preview_roster_import(
    db: Session,
    *,
    classroom_id: str,
    filename: str,
    content: bytes,
) -> ImportPreviewResult:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")

    raw_rows = _extract_tabular_rows(filename, content)
    non_empty = [r for r in raw_rows if any(cell for cell in r)]
    if len(non_empty) < 2:
        raise HTTPException(
            status_code=400,
            detail="Tệp cần có ít nhất 1 dòng tiêu đề và 1 dòng dữ liệu học sinh.",
        )

    code_idx, name_idx, note_idx = _locate_columns(non_empty[0])

    existing_students = {
        s.roster_code: s for s in db.execute(select(Student)).scalars().all()
    }
    same_class_ids = set(
        db.execute(
            select(ClassMembership.student_id).where(
                ClassMembership.classroom_id == classroom_id,
                ClassMembership.active_to.is_(None),
            )
        )
        .scalars()
        .all()
    )

    seen_in_file: set[str] = set()
    preview_rows: list[ImportPreviewRow] = []
    new_count = 0
    conflict_count = 0
    invalid_count = 0

    for offset, row in enumerate(non_empty[1:], start=2):
        code = row[code_idx].strip().upper() if code_idx < len(row) else ""
        name = row[name_idx].strip() if name_idx < len(row) else ""
        note = row[note_idx].strip() if note_idx is not None and note_idx < len(row) else ""

        if not code or not name:
            invalid_count += 1
            preview_rows.append(
                ImportPreviewRow(
                    row_number=offset,
                    roster_code=code,
                    full_name=name,
                    note=note,
                    status="INVALID",
                    message="Thiếu mã học sinh hoặc họ tên.",
                )
            )
            continue

        if code in seen_in_file:
            conflict_count += 1
            preview_rows.append(
                ImportPreviewRow(
                    row_number=offset,
                    roster_code=code,
                    full_name=name,
                    note=note,
                    status="DUPLICATE_IN_FILE",
                    message=f"Trùng mã '{code}' ngay trong file import.",
                )
            )
            continue

        seen_in_file.add(code)

        if code in existing_students:
            existing = existing_students[code]
            conflict_count += 1
            if existing.id in same_class_ids:
                preview_rows.append(
                    ImportPreviewRow(
                        row_number=offset,
                        roster_code=code,
                        full_name=name,
                        note=note,
                        status="EXISTS_SAME_CLASS",
                        message=f"Đã có trong lớp với tên '{existing.full_name}'.",
                    )
                )
            else:
                preview_rows.append(
                    ImportPreviewRow(
                        row_number=offset,
                        roster_code=code,
                        full_name=name,
                        note=note,
                        status="EXISTS_OTHER_CLASS",
                        message=f"Mã thuộc học sinh '{existing.full_name}' ở lớp khác.",
                    )
                )
            continue

        new_count += 1
        preview_rows.append(
            ImportPreviewRow(
                row_number=offset,
                roster_code=code,
                full_name=name,
                note=note,
                status="NEW",
                message="Hợp lệ — sẽ thêm mới.",
            )
        )

    return ImportPreviewResult(
        rows=preview_rows,
        new_count=new_count,
        conflict_count=conflict_count,
        invalid_count=invalid_count,
        has_conflicts=conflict_count > 0 or invalid_count > 0,
    )


def commit_roster_import(
    db: Session,
    *,
    classroom_id: str,
    teacher_id: int,
    rows: list[tuple[str, str, str]],
    duplicate_policy: Literal["skip", "update_name", "fail"] = "skip",
) -> dict[str, int]:
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học.")

    added = 0
    updated = 0
    skipped = 0
    seen_codes: set[str] = set()

    for raw_code, raw_name, raw_note in rows:
        code = raw_code.strip().upper()
        name = raw_name.strip()
        note = raw_note.strip()
        if not code or not name:
            skipped += 1
            continue
        if code in seen_codes:
            if duplicate_policy == "fail":
                raise HTTPException(status_code=409, detail=f"Trùng mã '{code}' trong danh sách.")
            skipped += 1
            continue
        seen_codes.add(code)

        existing = db.execute(select(Student).where(Student.roster_code == code)).scalar_one_or_none()
        if existing is not None:
            if duplicate_policy == "fail":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Xung đột mã học sinh '{code}' đã tồn tại.",
                )
            if duplicate_policy == "update_name":
                existing.full_name = name
                existing.updated_at = datetime.now(UTC)
                membership = db.execute(
                    select(ClassMembership).where(
                        ClassMembership.classroom_id == classroom_id,
                        ClassMembership.student_id == existing.id,
                        ClassMembership.active_to.is_(None),
                    )
                ).scalar_one_or_none()
                if membership is None:
                    db.add(
                        ClassMembership(
                            classroom_id=classroom_id,
                            student_id=existing.id,
                            active_from=datetime.now(UTC),
                        )
                    )
                updated += 1
            else:
                skipped += 1
            continue

        student = Student(
            id=str(uuid.uuid4()),
            roster_code=code,
            full_name=name,
            metadata_json=json.dumps({"note": note}, ensure_ascii=False) if note else "{}",
        )
        db.add(student)
        db.flush()
        db.add(
            ClassMembership(
                classroom_id=classroom_id,
                student_id=student.id,
                active_from=datetime.now(UTC),
            )
        )
        added += 1

    record_audit_event(
        db,
        actor_type="teacher",
        actor_id=str(teacher_id),
        action="COMMIT_ROSTER_IMPORT",
        target_type="classroom",
        target_id=classroom_id,
        details={"added": added, "updated": updated, "skipped": skipped, "policy": duplicate_policy},
    )
    db.commit()
    return {"added": added, "updated": updated, "skipped": skipped}
