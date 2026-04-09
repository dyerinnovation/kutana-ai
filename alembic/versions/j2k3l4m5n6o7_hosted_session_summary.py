"""Add summary_text column to hosted_agent_sessions.

Stores agent summary responses at meeting end so they are
persisted in the database and not lost after Redis delivery.

Revision ID: j2k3l4m5n6o7
Revises: i1a2b3c4d5e6
Create Date: 2026-04-09 12:00:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "j2k3l4m5n6o7"
down_revision = "i1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add summary_text column to hosted_agent_sessions."""
    op.add_column(
        "hosted_agent_sessions",
        sa.Column("summary_text", sa.Text, nullable=True),
    )


def downgrade() -> None:
    """Remove summary_text column from hosted_agent_sessions."""
    op.drop_column("hosted_agent_sessions", "summary_text")
