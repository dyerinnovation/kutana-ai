"""Add system_prompt_override column to hosted_agent_sessions.

Revision ID: h2b3c4d5e6f7
Revises: h1a2b3c4d5e6
Create Date: 2026-04-06 18:30:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "h2b3c4d5e6f7"
down_revision = "h1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable system_prompt_override column."""
    op.add_column(
        "hosted_agent_sessions",
        sa.Column("system_prompt_override", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove system_prompt_override column."""
    op.drop_column("hosted_agent_sessions", "system_prompt_override")
