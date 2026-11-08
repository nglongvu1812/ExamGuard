"""Add exam engine fields, permutations, answer revisions, submissions, and backup manifests.

Revision ID: 0004_exam_engine_and_answers
Revises: 0003_question_bank_and_converter
Create Date: 2026-11-08 18:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_exam_engine_and_answers"
down_revision: str | Sequence[str] | None = "0003_question_bank_and_converter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("exams") as batch_op:
        batch_op.add_column(sa.Column("seed", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("shuffle_questions", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("shuffle_options", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("paused_total_s", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "policy_json",
                sa.Text(),
                nullable=False,
                server_default='{"heartbeat_s": 3, "suspected_s": 5, "disconnect_s": 15, "grace_submit_s": 30}',
            )
        )

    with op.batch_alter_table("attempts") as batch_op:
        batch_op.add_column(sa.Column("extra_time_s", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "question_version_id", name="uq_exam_question_ver"),
    )
    op.create_index("ix_exam_questions_exam_id", "exam_questions", ["exam_id"])
    op.create_index("ix_exam_questions_question_version_id", "exam_questions", ["question_version_id"])

    op.create_table(
        "exam_permutations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("question_order_json", sa.Text(), nullable=False),
        sa.Column("option_order_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "student_id", name="uq_perm_exam_student"),
    )
    op.create_index("ix_exam_permutations_exam_id", "exam_permutations", ["exam_id"])
    op.create_index("ix_exam_permutations_student_id", "exam_permutations", ["student_id"])

    op.create_table(
        "answer_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("question_version_id", sa.String(length=36), nullable=False),
        sa.Column("selected_option_ids_json", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("client_timestamp", sa.String(length=64), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["question_version_id"], ["question_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "idempotency_key", name="uq_answer_attempt_idempotency"),
    )
    op.create_index("ix_answer_revisions_attempt_id", "answer_revisions", ["attempt_id"])
    op.create_index("ix_answer_revisions_question_version_id", "answer_revisions", ["question_version_id"])

    op.create_table(
        "submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("answer_snapshot_json", sa.Text(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("submission_mode", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", name="uq_submission_attempt"),
    )
    op.create_index("ix_submissions_attempt_id", "submissions", ["attempt_id"])
    op.create_index("ix_submissions_exam_id", "submissions", ["exam_id"])
    op.create_index("ix_submissions_student_id", "submissions", ["student_id"])

    op.create_table(
        "backup_manifests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("record_counts_json", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("backup_manifests")
    op.drop_index("ix_submissions_student_id", table_name="submissions")
    op.drop_index("ix_submissions_exam_id", table_name="submissions")
    op.drop_index("ix_submissions_attempt_id", table_name="submissions")
    op.drop_table("submissions")
    op.drop_index("ix_answer_revisions_question_version_id", table_name="answer_revisions")
    op.drop_index("ix_answer_revisions_attempt_id", table_name="answer_revisions")
    op.drop_table("answer_revisions")
    op.drop_index("ix_exam_permutations_student_id", table_name="exam_permutations")
    op.drop_index("ix_exam_permutations_exam_id", table_name="exam_permutations")
    op.drop_table("exam_permutations")
    op.drop_index("ix_exam_questions_question_version_id", table_name="exam_questions")
    op.drop_index("ix_exam_questions_exam_id", table_name="exam_questions")
    op.drop_table("exam_questions")

    with op.batch_alter_table("attempts") as batch_op:
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("extra_time_s")

    with op.batch_alter_table("exams") as batch_op:
        batch_op.drop_column("policy_json")
        batch_op.drop_column("closed_at")
        batch_op.drop_column("paused_total_s")
        batch_op.drop_column("paused_at")
        batch_op.drop_column("deadline_at")
        batch_op.drop_column("start_at")
        batch_op.drop_column("shuffle_options")
        batch_op.drop_column("shuffle_questions")
        batch_op.drop_column("seed")
