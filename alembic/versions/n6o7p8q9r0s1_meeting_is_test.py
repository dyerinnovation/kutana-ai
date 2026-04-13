"""Add is_test_meeting flag to meetings.

Lets the eval harness mark meetings it creates so they can be safely
deleted on job teardown without touching real user meetings.

Revision ID: n6o7p8q9r0s1
Revises: m5n6o7p8q9r0
Create Date: 2026-04-12 00:00:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "n6o7p8q9r0s1"
down_revision = "m5n6o7p8q9r0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_test_meeting column."""
    op.add_column(
        "meetings",
        sa.Column(
            "is_test_meeting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Drop is_test_meeting column."""
    op.drop_column("meetings", "is_test_meeting")
