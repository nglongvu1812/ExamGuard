"""ORM models for ExamGuard foundation, roster, invites, attempts, and audit log."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.base import Base
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    """Exam session entity with lifecycle state, deterministic shuffle seed, and server timer."""

    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey("classrooms.id"), nullable=False, index=True)
    room_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False, default=2700)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="WAITING")
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_total_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=(
            '{"heartbeat_s": 3, "suspected_s": 5, '
            '"disconnect_s": 15, "lock_after_s": 30, "grace_submit_s": 30}'
        ),
    )
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
    invite_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    presence_state: Mapped[str] = mapped_column(String(32), nullable=False, default="OFFLINE")
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconnect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hidden_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_time_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    correct_option_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(
        String(300), nullable=False, default="Khởi tạo khi duyệt câu hỏi"
    )
    approved_by: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class ExamQuestion(Base):
    """Approved question versions locked into a specific exam."""

    __tablename__ = "exam_questions"
    __table_args__ = (UniqueConstraint("exam_id", "question_version_id", name="uq_exam_question_ver"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)


class ExamPermutation(Base):
    """Frozen seeded question & option order per student (option_ids stay invariant)."""

    __tablename__ = "exam_permutations"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_perm_exam_student"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    question_order_json: Mapped[str] = mapped_column(Text, nullable=False)
    option_order_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class AnswerRevision(Base):
    """Idempotent append-only answer write log committed prior to ACK."""

    __tablename__ = "answer_revisions"
    __table_args__ = (
        UniqueConstraint("attempt_id", "idempotency_key", name="uq_answer_attempt_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False, index=True)
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False, index=True
    )
    selected_option_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    client_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class Submission(Base):
    """Immutable canonical snapshot of a student's final answers upon submission."""

    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("attempt_id", name="uq_submission_attempt"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    answer_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    submission_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="student_submit")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class BackupManifest(Base):
    """Records verified backup snapshots with SHA-256 checksums."""

    __tablename__ = "backup_manifests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    record_counts_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PresenceEvent(Base):
    """Timestamped client/network telemetry signals; never proves misconduct on its own."""

    __tablename__ = "presence_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    server_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class Incident(Base):
    """Non-punitive technical or procedural verification incident awaiting teacher action."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    trigger_type: Mapped[str] = mapped_column(String(48), nullable=False)
    summary: Mapped[str] = mapped_column(String(250), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)


class GradeRun(Base):
    """Immutable grading provenance snapshot capturing code, rubric, and answer keys used."""

    __tablename__ = "grade_runs"
    __table_args__ = (UniqueConstraint("exam_id", "run_number", name="uq_grade_run_exam_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    code_version: Mapped[str] = mapped_column(String(48), nullable=False, default="scoring-v1.0")
    rubric_version_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    key_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    reason: Mapped[str] = mapped_column(String(300), nullable=False, default="Chấm điểm tự động")
    triggered_by: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class ScoreVersion(Base):
    """Append-only student score version linked to its immutable Submission and GradeRun."""

    __tablename__ = "score_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id"), nullable=False, index=True
    )
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    grade_run_id: Mapped[str] = mapped_column(ForeignKey("grade_runs.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    raw_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    earned_points: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_10: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reason: Mapped[str] = mapped_column(String(300), nullable=False, default="Chấm lần đầu")
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("score_versions.id"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class ReceiptVersion(Base):
    """Published personal result receipt version with PDF/PNG artifact hashes and supersession."""

    __tablename__ = "receipt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    score_version_id: Mapped[str] = mapped_column(
        ForeignKey("score_versions.id"), nullable=False, index=True
    )
    receipt_code: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pdf_relpath: Mapped[str] = mapped_column(String(255), nullable=False)
    png_relpath: Mapped[str] = mapped_column(String(255), nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("receipt_versions.id"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class PaperVersion(Base):
    """Deterministic printed paper variant (Mã đề) reusing canonical option_id key mapping."""

    __tablename__ = "paper_versions"
    __table_args__ = (UniqueConstraint("exam_id", "version_code", name="uq_paper_exam_version_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    version_code: Mapped[str] = mapped_column(String(16), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    question_order_json: Mapped[str] = mapped_column(Text, nullable=False)
    option_order_json: Mapped[str] = mapped_column(Text, nullable=False)
    answer_key_map_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class OmrScanSubmission(Base):
    """Immutable scanned OMR sheet with alignment telemetry, confidence scores, and teacher review gate."""

    __tablename__ = "omr_scan_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    paper_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper_versions.id"), nullable=True, index=True
    )
    roster_code_detected: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    version_code_detected: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    source_image_relpath: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    aligned_preview_relpath: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    detected_answers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confirmed_answers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    ambiguous_questions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_REVIEW")
    linked_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("attempts.id"), nullable=True)
    linked_submission_id: Mapped[str | None] = mapped_column(ForeignKey("submissions.id"), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("teacher_profiles.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
