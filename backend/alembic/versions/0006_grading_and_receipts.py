"""Add grading provenance, score/receipt versioning, answer key metadata, and exam review/publish timestamps.

Revision ID: 0006_grading_and_receipts
Revises: 0005_monitoring_and_incidents
Create Date: 2026-11-08 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_grading_and_receipts"
down_revision: str | Sequence[str] | None = "0005_monitoring_and_incidents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("exams") as batch_op:
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("answer_key_versions") as batch_op:
        batch_op.add_column(
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column(
                "reason",
                sa.String(length=300),
                nullable=False,
                server_default="Khởi tạo khi duyệt câu hỏi",
            )
        )

    op.create_table(
        "grade_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("code_version", sa.String(length=48), nullable=False, server_default="scoring-v1.0"),
        sa.Column("rubric_version_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("key_snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default="Chấm điểm tự động"),
        sa.Column("triggered_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["triggered_by"], ["teacher_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "run_number", name="uq_grade_run_exam_number"),
    )
    op.create_index("ix_grade_runs_exam_id", "grade_runs", ["exam_id"])

    op.create_table(
        "score_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("grade_run_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("raw_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("earned_points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score_10", sa.Float(), nullable=False, server_default="0"),
        sa.Column("breakdown_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default="Chấm lần đầu"),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["grade_run_id"], ["grade_runs.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["score_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_score_versions_attempt_id", "score_versions", ["attempt_id"])
    op.create_index("ix_score_versions_exam_id", "score_versions", ["exam_id"])
    op.create_index("ix_score_versions_grade_run_id", "score_versions", ["grade_run_id"])
    op.create_index("ix_score_versions_student_id", "score_versions", ["student_id"])
    op.create_index("ix_score_versions_submission_id", "score_versions", ["submission_id"])

    op.create_table(
        "receipt_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("score_version_id", sa.String(length=36), nullable=False),
        sa.Column("receipt_code", sa.String(length=48), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pdf_relpath", sa.String(length=255), nullable=False),
        sa.Column("png_relpath", sa.String(length=255), nullable=False),
        sa.Column("document_sha256", sa.String(length=64), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["score_version_id"], ["score_versions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["receipt_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipt_versions_exam_id", "receipt_versions", ["exam_id"])
    op.create_index("ix_receipt_versions_receipt_code", "receipt_versions", ["receipt_code"])
    op.create_index("ix_receipt_versions_score_version_id", "receipt_versions", ["score_version_id"])
    op.create_index("ix_receipt_versions_student_id", "receipt_versions", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_receipt_versions_student_id", table_name="receipt_versions")
    op.drop_index("ix_receipt_versions_score_version_id", table_name="receipt_versions")
    op.drop_index("ix_receipt_versions_receipt_code", table_name="receipt_versions")
    op.drop_index("ix_receipt_versions_exam_id", table_name="receipt_versions")
    op.drop_table("receipt_versions")

    op.drop_index("ix_score_versions_submission_id", table_name="score_versions")
    op.drop_index("ix_score_versions_student_id", table_name="score_versions")
    op.drop_index("ix_score_versions_grade_run_id", table_name="score_versions")
    op.drop_index("ix_score_versions_exam_id", table_name="score_versions")
    op.drop_index("ix_score_versions_attempt_id", table_name="score_versions")
    op.drop_table("score_versions")

    op.drop_index("ix_grade_runs_exam_id", table_name="grade_runs")
    op.drop_table("grade_runs")

    with op.batch_alter_table("answer_key_versions") as batch_op:
        batch_op.drop_column("reason")
        batch_op.drop_column("version_number")

    with op.batch_alter_table("exams") as batch_op:
        batch_op.drop_column("published_at")
        batch_op.drop_column("reviewed_at")
