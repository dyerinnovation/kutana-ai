"""Add participation_mode column to agent_templates.

Distinguishes observer agents (silent, respond via chat) from
participant agents (raise hand, speak, facilitate discussion).
All agents receive real-time transcript segments.

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-04-09 14:00:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "k3l4m5n6o7p8"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None

# Participant agents: actively facilitate meetings
_PARTICIPANT_IDS = (
    "'a0000000-0000-0000-0000-000000000003'",  # Standup Facilitator
    "'a0000000-0000-0000-0000-000000000007'",  # Sprint Retro Coach
    "'a0000000-0000-0000-0000-000000000008'",  # Sprint Planner
    "'a0000000-0000-0000-0000-000000000009'",  # User Interviewer
    "'a0000000-0000-0000-0000-00000000000a'",  # Initial Interviewer
)


def upgrade() -> None:
    """Add participation_mode column and set values for existing templates."""
    op.add_column(
        "agent_templates",
        sa.Column(
            "participation_mode",
            sa.String(20),
            nullable=False,
            server_default="observer",
        ),
    )

    # Set participant mode for active facilitation agents
    op.execute(
        f"""
        UPDATE agent_templates
        SET participation_mode = 'participant'
        WHERE id IN ({", ".join(_PARTICIPANT_IDS)})
        """
    )


def downgrade() -> None:
    """Remove participation_mode column."""
    op.drop_column("agent_templates", "participation_mode")
