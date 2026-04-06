"""Add owner_id to meetings and create meeting_invites table.

Revision ID: a2b3c4d5e6f7
Revises: f7a8b9c0d1e2
Create Date: 2026-04-05
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a2b3c4d5e6f7"
down_revision: str = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add owner_id column to meetings
    op.add_column(
        "meetings",
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_meetings_owner_id", "meetings", ["owner_id"])

    # Create meeting_invites table
    op.create_table(
        "meeting_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="accepted"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("meeting_id", "user_id", name="uq_meeting_invite"),
    )
    op.create_index("ix_meeting_invites_user_id", "meeting_invites", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meeting_invites_user_id", table_name="meeting_invites")
    op.drop_table("meeting_invites")
    op.drop_index("ix_meetings_owner_id", table_name="meetings")
    op.drop_column("meetings", "owner_id")
