"""Add meeting_selected_templates join table.

Source of truth for which agent templates a meeting has selected.
``POST /v1/meetings/{id}/start`` reads this table and fires one
background warm per row so activation is decoupled from checkbox
selection.

Revision ID: l4m5n6o7p8q9
Revises: k3l4m5n6o7p8
Create Date: 2026-04-10 12:00:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "l4m5n6o7p8q9"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the meeting_selected_templates table."""
    op.create_table(
        "meeting_selected_templates",
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("system_prompt_override", sa.Text(), nullable=True),
        sa.Column("sop_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["agent_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sop_id"], ["organization_sops.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("meeting_id", "template_id"),
    )
    op.create_index(
        "ix_meeting_selected_templates_meeting_id",
        "meeting_selected_templates",
        ["meeting_id"],
    )
    op.create_index(
        "ix_meeting_selected_templates_template_id",
        "meeting_selected_templates",
        ["template_id"],
    )


def downgrade() -> None:
    """Drop the meeting_selected_templates table."""
    op.drop_index(
        "ix_meeting_selected_templates_template_id",
        table_name="meeting_selected_templates",
    )
    op.drop_index(
        "ix_meeting_selected_templates_meeting_id",
        table_name="meeting_selected_templates",
    )
    op.drop_table("meeting_selected_templates")
