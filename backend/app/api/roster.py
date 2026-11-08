"""Classroom and student roster CRUD + CSV/XLSX dry-run import API."""

from __future__ import annotations

from typing import Literal

from app.api.deps import get_db
from app.security.auth import TeacherPrincipal, require_teacher
from app.services.roster_service import (
    archive_classroom,
    archive_student,
    commit_roster_import,
    create_classroom,
    create_student_in_classroom,
    list_classroom_students,
    list_classrooms,
    preview_roster_import,
    update_student,
)
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1", tags=["roster"])


class ClassroomCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    academic_year: str = Field(default="2026-2027", max_length=32)


class ClassroomDTO(BaseModel):
    id: str
    name: str
    academic_year: str
    student_count: int
    archived: bool


class StudentCreateRequest(BaseModel):
    roster_code: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=250)


class StudentUpdateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)


class StudentDTO(BaseModel):
    id: str
    roster_code: str
    full_name: str
    archived: bool


class ImportPreviewRowDTO(BaseModel):
    row_number: int
    roster_code: str
    full_name: str
    note: str
    status: str
    message: str


class ImportPreviewResponse(BaseModel):
    rows: list[ImportPreviewRowDTO]
    new_count: int
    conflict_count: int
    invalid_count: int
    has_conflicts: bool


class ImportCommitRow(BaseModel):
    roster_code: str
    full_name: str
    note: str = ""


class ImportCommitRequest(BaseModel):
    rows: list[ImportCommitRow]
    duplicate_policy: Literal["skip", "update_name", "fail"] = "skip"


class ImportCommitResponse(BaseModel):
    added: int
    updated: int
    skipped: int


@router.get("/classes", response_model=list[ClassroomDTO])
def get_classes(
    include_archived: bool = Query(default=False),
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[ClassroomDTO]:
    items = list_classrooms(db, teacher_id=teacher.teacher_id, include_archived=include_archived)
    return [
        ClassroomDTO(
            id=cls.id,
            name=cls.name,
            academic_year=cls.academic_year,
            student_count=count,
            archived=cls.archived_at is not None,
        )
        for cls, count in items
    ]


@router.post("/classes", response_model=ClassroomDTO, status_code=201)
def post_class(
    payload: ClassroomCreateRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ClassroomDTO:
    cls = create_classroom(
        db,
        teacher_id=teacher.teacher_id,
        name=payload.name,
        academic_year=payload.academic_year,
    )
    return ClassroomDTO(
        id=cls.id,
        name=cls.name,
        academic_year=cls.academic_year,
        student_count=0,
        archived=False,
    )


@router.delete("/classes/{classroom_id}", response_model=ClassroomDTO)
def delete_class(
    classroom_id: str,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ClassroomDTO:
    cls = archive_classroom(db, classroom_id=classroom_id, teacher_id=teacher.teacher_id)
    return ClassroomDTO(
        id=cls.id,
        name=cls.name,
        academic_year=cls.academic_year,
        student_count=0,
        archived=cls.archived_at is not None,
    )


@router.get("/classes/{classroom_id}/students", response_model=list[StudentDTO])
def get_students(
    classroom_id: str,
    include_archived: bool = Query(default=False),
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[StudentDTO]:
    students = list_classroom_students(
        db,
        classroom_id=classroom_id,
        include_archived=include_archived,
    )
    return [
        StudentDTO(
            id=st.id,
            roster_code=st.roster_code,
            full_name=st.full_name,
            archived=st.archived_at is not None,
        )
        for st in students
    ]


@router.post("/classes/{classroom_id}/students", response_model=StudentDTO, status_code=201)
def post_student(
    classroom_id: str,
    payload: StudentCreateRequest,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> StudentDTO:
    st = create_student_in_classroom(
        db,
        classroom_id=classroom_id,
        roster_code=payload.roster_code,
        full_name=payload.full_name,
        note=payload.note,
    )
    return StudentDTO(
        id=st.id,
        roster_code=st.roster_code,
        full_name=st.full_name,
        archived=st.archived_at is not None,
    )


@router.patch("/students/{student_id}", response_model=StudentDTO)
def patch_student(
    student_id: str,
    payload: StudentUpdateRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> StudentDTO:
    st = update_student(
        db,
        student_id=student_id,
        full_name=payload.full_name,
        teacher_id=teacher.teacher_id,
    )
    return StudentDTO(
        id=st.id,
        roster_code=st.roster_code,
        full_name=st.full_name,
        archived=st.archived_at is not None,
    )


@router.delete("/students/{student_id}", response_model=StudentDTO)
def delete_student(
    student_id: str,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> StudentDTO:
    st = archive_student(db, student_id=student_id, teacher_id=teacher.teacher_id)
    return StudentDTO(
        id=st.id,
        roster_code=st.roster_code,
        full_name=st.full_name,
        archived=st.archived_at is not None,
    )


@router.post("/classes/{classroom_id}/import/preview", response_model=ImportPreviewResponse)
async def post_import_preview(
    classroom_id: str,
    file: UploadFile = File(...),
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    content = await file.read()
    res = preview_roster_import(
        db,
        classroom_id=classroom_id,
        filename=file.filename or "roster.csv",
        content=content,
    )
    return ImportPreviewResponse(
        rows=[
            ImportPreviewRowDTO(
                row_number=r.row_number,
                roster_code=r.roster_code,
                full_name=r.full_name,
                note=r.note,
                status=r.status,
                message=r.message,
            )
            for r in res.rows
        ],
        new_count=res.new_count,
        conflict_count=res.conflict_count,
        invalid_count=res.invalid_count,
        has_conflicts=res.has_conflicts,
    )


@router.post("/classes/{classroom_id}/import/commit", response_model=ImportCommitResponse)
def post_import_commit(
    classroom_id: str,
    payload: ImportCommitRequest,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> ImportCommitResponse:
    summary = commit_roster_import(
        db,
        classroom_id=classroom_id,
        teacher_id=teacher.teacher_id,
        rows=[(r.roster_code, r.full_name, r.note) for r in payload.rows],
        duplicate_policy=payload.duplicate_policy,
    )
    return ImportCommitResponse(**summary)
