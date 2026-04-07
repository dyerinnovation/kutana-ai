"""Mark Standup Facilitator and Technical Scribe as premium templates.

Revision ID: h1a2b3c4d5e6
Revises: g8b9c0d1e2f3
Create Date: 2026-04-06 18:00:00.000000+00:00
"""

from alembic import op

revision = "h1a2b3c4d5e6"
down_revision = "g8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Set is_premium = true for Pro-tier managed agent templates."""
    op.execute(
        """
        UPDATE agent_templates SET is_premium = true
        WHERE name IN ('Standup Facilitator', 'Technical Scribe')
        """
    )


def downgrade() -> None:
    """Revert premium templates back to basic."""
    op.execute(
        """
        UPDATE agent_templates SET is_premium = false
        WHERE name IN ('Standup Facilitator', 'Technical Scribe')
        """
    )
