"""Add error_detail to hosted_agent_sessions.

Persists the failure reason when a background-warmed managed agent
activation fails, so ``GET /v1/meetings/{id}/agent-sessions`` can expose
it to the frontend's per-agent spinner and the retry endpoint can be
fired by the user.

Revision ID: m5n6o7p8q9r0
Revises: l4m5n6o7p8q9
Create Date: 2026-04-10 14:00:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "m5n6o7p8q9r0"
down_revision = "l4m5n6o7p8q9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add error_detail column."""
    op.add_column(
        "hosted_agent_sessions",
        sa.Column("error_detail", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Drop error_detail column."""
    op.drop_column("hosted_agent_sessions", "error_detail")
