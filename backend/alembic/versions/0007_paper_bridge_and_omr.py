"""Add paper_versions and omr_scan_submissions tables for paper exam booklets & OMR bridge.

Revision ID: 0007_paper_bridge_and_omr
Revises: 0006_grading_and_receipts
Create Date: 2026-11-08 19:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_paper_bridge_and_omr"
down_revision: str | Sequence[str] | None = "0006_grading_and_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("version_code", sa.String(length=16), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("question_order_json", sa.Text(), nullable=False),
        sa.Column("option_order_json", sa.Text(), nullable=False),
        sa.Column("answer_key_map_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["teacher_profiles.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "version_code", name="uq_paper_exam_version_code"),
    )
    op.create_index("ix_paper_versions_exam_id", "paper_versions", ["exam_id"])

    op.create_table(
        "omr_scan_submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=True),
        sa.Column("paper_version_id", sa.String(length=36), nullable=True),
        sa.Column("roster_code_detected", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("version_code_detected", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("source_image_relpath", sa.String(length=255), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("aligned_preview_relpath", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("detected_answers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("confirmed_answers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("confidence_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ambiguous_questions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("overall_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("linked_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("linked_submission_id", sa.String(length=36), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["confirmed_by"], ["teacher_profiles.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["linked_attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["linked_submission_id"], ["submissions.id"]),
        sa.ForeignKeyConstraint(["paper_version_id"], ["paper_versions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_omr_scan_submissions_exam_id", "omr_scan_submissions", ["exam_id"])
    op.create_index(
        "ix_omr_scan_submissions_paper_version_id", "omr_scan_submissions", ["paper_version_id"]
    )
    op.create_index("ix_omr_scan_submissions_student_id", "omr_scan_submissions", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_omr_scan_submissions_student_id", table_name="omr_scan_submissions")
    op.drop_index("ix_omr_scan_submissions_paper_version_id", table_name="omr_scan_submissions")
    op.drop_index("ix_omr_scan_submissions_exam_id", table_name="omr_scan_submissions")
    op.drop_table("omr_scan_submissions")

    op.drop_index("ix_paper_versions_exam_id", table_name="paper_versions")
    op.drop_table("paper_versions")
