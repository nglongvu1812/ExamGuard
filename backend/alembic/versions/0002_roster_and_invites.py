"""Add roster, exam waiting room, invites, attempts, device bindings, and audit events.

Revision ID: 0002_roster_and_invites
Revises: 0001_initial_foundation
Create Date: 2026-11-08 18:22:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_roster_and_invites"
down_revision: str | Sequence[str] | None = "0001_initial_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "classrooms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("academic_year", sa.String(length=32), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "teacher_id", "academic_year", "name", name="uq_classroom_teacher_year_name"
        ),
    )
    op.create_table(
        "students",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("roster_code", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_students_roster_code", "students", ["roster_code"], unique=True)

    op.create_table(
        "class_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classroom_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_class_memberships_classroom_id", "class_memberships", ["classroom_id"])
    op.create_index("ix_class_memberships_student_id", "class_memberships", ["student_id"])

    op.create_table(
        "exams",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("classroom_id", sa.String(length=36), nullable=False),
        sa.Column("room_code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exams_classroom_id", "exams", ["classroom_id"])
    op.create_index("ix_exams_room_code", "exams", ["room_code"], unique=True)

    op.create_table(
        "student_invites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_invites_exam_id", "student_invites", ["exam_id"])
    op.create_index("ix_student_invites_student_id", "student_invites", ["student_id"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "student_id", name="uq_attempt_exam_student"),
    )
    op.create_index("ix_attempts_exam_id", "attempts", ["exam_id"])
    op.create_index("ix_attempts_student_id", "attempts", ["student_id"])

    op.create_table(
        "device_bindings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("device_token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_agent_hint", sa.String(length=200), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_device_bindings_attempt_id", "device_bindings", ["attempt_id"])
    op.create_index("ix_device_bindings_exam_id", "device_bindings", ["exam_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("before_hash", sa.String(length=64), nullable=False),
        sa.Column("after_hash", sa.String(length=64), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_index("ix_device_bindings_exam_id", table_name="device_bindings")
    op.drop_index("ix_device_bindings_attempt_id", table_name="device_bindings")
    op.drop_table("device_bindings")
    op.drop_index("ix_attempts_student_id", table_name="attempts")
    op.drop_index("ix_attempts_exam_id", table_name="attempts")
    op.drop_table("attempts")
    op.drop_index("ix_student_invites_student_id", table_name="student_invites")
    op.drop_index("ix_student_invites_exam_id", table_name="student_invites")
    op.drop_table("student_invites")
    op.drop_index("ix_exams_room_code", table_name="exams")
    op.drop_index("ix_exams_classroom_id", table_name="exams")
    op.drop_table("exams")
    op.drop_index("ix_class_memberships_student_id", table_name="class_memberships")
    op.drop_index("ix_class_memberships_classroom_id", table_name="class_memberships")
    op.drop_table("class_memberships")
    op.drop_index("ix_students_roster_code", table_name="students")
    op.drop_table("students")
    op.drop_table("classrooms")
