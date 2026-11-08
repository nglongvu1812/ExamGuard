"""Add invite_code column to student_invites for teacher waiting room display.

Revision ID: 0008_student_invite_plaintext_code
Revises: 0007_paper_bridge_and_omr
Create Date: 2026-11-08 22:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_student_invite_plaintext_code"
down_revision: str | Sequence[str] | None = "0007_paper_bridge_and_omr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("student_invites", sa.Column("invite_code", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("student_invites", "invite_code")
