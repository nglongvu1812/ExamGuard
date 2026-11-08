"""ORM models for ExamGuard foundation, roster, invites, attempts, and audit log."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.base import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class SystemMetadata(Base):
    """Stores schema metadata, install ID, and local settings flags."""

    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class TeacherProfile(Base):
    """Local teacher profile owning classrooms and exams."""

    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Giáo viên")
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class Classroom(Base):
    """Classroom owned by a teacher with soft-archive support."""

    __tablename__ = "classrooms"
    __table_args__ = (
        UniqueConstraint("teacher_id", "academic_year", "name", name="uq_classroom_teacher_year_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(32), nullable=False, default="2026-2027")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class Student(Base):
    """Student identity with stable UUID and unique roster_code."""

    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    roster_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class ClassMembership(Base):
    """Historical classroom membership for a student without mutating past scores."""

    __tablename__ = "class_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey("classrooms.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    active_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Exam(Base):
    """Exam session entity (P1 minimal waiting-room shell; expanded in P3)."""

    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey("classrooms.id"), nullable=False, index=True)
    room_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False, default=2700)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="WAITING")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class StudentInvite(Base):
    """Hashed per-student invite code for joining an exam room."""

    __tablename__ = "student_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Attempt(Base):
    """Single active attempt per (exam, student) enforced at database level."""

    __tablename__ = "attempts"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_attempt_exam_student"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_APPROVAL")
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    latest_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class DeviceBinding(Base):
    """Best-effort browser-scoped token hash bound to a student attempt."""

    __tablename__ = "device_bindings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False, index=True)
    device_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    user_agent_hint: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    """Append-only hash-chained audit log for critical actions."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    before_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    after_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class SourceDocument(Base):
    """Immutable uploaded source exam file with SHA-256 checksum."""

    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    relpath: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class Asset(Base):
    """Content-addressed media asset extracted offline into ExamGuardData/assets."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 hex
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    relpath: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class ImportJob(Base):
    """Tracks document conversion runs and warnings."""

    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="COMPLETED")
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False, default="docx-v1.0")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class QuestionDraft(Base):
    """Editable parsed question candidate awaiting teacher confirmation."""

    __tablename__ = "question_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    import_job_id: Mapped[str] = mapped_column(ForeignKey("import_jobs.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False, default="single_choice")
    blocks_json: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    answer_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_json: Mapped[str] = mapped_column(Text, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    confidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    approved_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Question(Base):
    """Logical question identity in the approved question bank."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Mặc định")
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class QuestionVersion(Base):
    """Immutable approved question snapshot."""

    __tablename__ = "question_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_blocks_json: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    approved_by: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class AnswerKeyVersion(Base):
    """Immutable answer key separated from question body to prevent early disclosure."""

    __tablename__ = "answer_key_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    correct_option_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
