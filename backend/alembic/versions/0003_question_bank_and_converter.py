"""Add question bank, source document, asset, import job, draft, and answer key tables.

Revision ID: 0003_question_bank_and_converter
Revises: 0002_roster_and_invites
Create Date: 2026-11-08 18:26:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_question_bank_and_converter"
down_revision: str | Sequence[str] | None = "0002_roster_and_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("relpath", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_documents_sha256", "source_documents", ["sha256"], unique=True)

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("relpath", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("error_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_jobs_document_id", "import_jobs", ["document_id"])

    op.create_table(
        "question_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("import_job_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("blocks_json", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("answer_json", sa.Text(), nullable=False),
        sa.Column("source_json", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("confidence_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_version_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_drafts_import_job_id", "question_drafts", ["import_job_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("active_version_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "question_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_blocks_json", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["teacher_profiles.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_versions_question_id", "question_versions", ["question_id"])

    op.create_table(
        "answer_key_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("correct_option_ids_json", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["teacher_profiles.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_answer_key_versions_question_version_id",
        "answer_key_versions",
        ["question_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_answer_key_versions_question_version_id", table_name="answer_key_versions")
    op.drop_table("answer_key_versions")
    op.drop_index("ix_question_versions_question_id", table_name="question_versions")
    op.drop_table("question_versions")
    op.drop_table("questions")
    op.drop_index("ix_question_drafts_import_job_id", table_name="question_drafts")
    op.drop_table("question_drafts")
    op.drop_index("ix_import_jobs_document_id", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_table("assets")
    op.drop_index("ix_source_documents_sha256", table_name="source_documents")
    op.drop_table("source_documents")
