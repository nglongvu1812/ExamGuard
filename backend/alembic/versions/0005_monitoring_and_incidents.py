"""Add presence_events, incidents tables and Attempt presence monitoring columns.

Revision ID: 0005_monitoring_and_incidents
Revises: 0004_exam_engine_and_answers
Create Date: 2026-11-08 18:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_monitoring_and_incidents"
down_revision: str | Sequence[str] | None = "0004_exam_engine_and_answers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attempts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "presence_state",
                sa.String(length=32),
                nullable=False,
                server_default="OFFLINE",
            )
        )
        batch_op.add_column(sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("reconnect_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("hidden_event_count", sa.Integer(), nullable=False, server_default="0")
        )

    op.create_table(
        "presence_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("server_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_presence_events_attempt_id", "presence_events", ["attempt_id"])
    op.create_index("ix_presence_events_exam_id", "presence_events", ["exam_id"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("exam_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("trigger_type", sa.String(length=48), nullable=False),
        sa.Column("summary", sa.String(length=250), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolution_reason", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["teacher_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_attempt_id", "incidents", ["attempt_id"])
    op.create_index("ix_incidents_exam_id", "incidents", ["exam_id"])


def downgrade() -> None:
    op.drop_index("ix_incidents_exam_id", table_name="incidents")
    op.drop_index("ix_incidents_attempt_id", table_name="incidents")
    op.drop_table("incidents")

    op.drop_index("ix_presence_events_exam_id", table_name="presence_events")
    op.drop_index("ix_presence_events_attempt_id", table_name="presence_events")
    op.drop_table("presence_events")

    with op.batch_alter_table("attempts") as batch_op:
        batch_op.drop_column("hidden_event_count")
        batch_op.drop_column("reconnect_count")
        batch_op.drop_column("last_heartbeat_at")
        batch_op.drop_column("presence_state")
