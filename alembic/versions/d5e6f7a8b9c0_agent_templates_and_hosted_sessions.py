"""Create agent_templates and hosted_agent_sessions tables with seed data.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-26
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("capabilities", JSONB(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_templates_category", "agent_templates", ["category"])

    op.create_table(
        "hosted_agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("anthropic_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["agent_templates.id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
    )
    op.create_index(
        "ix_hosted_agent_sessions_user_id", "hosted_agent_sessions", ["user_id"]
    )
    op.create_index(
        "ix_hosted_agent_sessions_meeting_id",
        "hosted_agent_sessions",
        ["meeting_id"],
    )
    op.create_index(
        "ix_hosted_agent_sessions_status", "hosted_agent_sessions", ["status"]
    )

    # Seed default templates
    op.execute(
        """
        INSERT INTO agent_templates (id, name, description, system_prompt, capabilities, category, is_premium)
        VALUES
        (
            'a0000000-0000-0000-0000-000000000001',
            'Meeting Notetaker',
            'Takes detailed notes during meetings and extracts action items automatically.',
            'You are a meeting notetaker. Listen carefully to the conversation, capture key discussion points, decisions made, and extract action items with assignees. Organize notes by topic.',
            '["transcription", "task_extraction", "action_items"]'::jsonb,
            'productivity',
            false
        ),
        (
            'a0000000-0000-0000-0000-000000000002',
            'Technical Scribe',
            'Captures technical decisions, architecture discussions, and engineering context.',
            'You are a technical scribe for engineering meetings. Focus on capturing technical decisions, architecture choices, trade-offs discussed, code references, and follow-up engineering tasks. Use precise technical language.',
            '["transcription", "task_extraction", "summarization"]'::jsonb,
            'engineering',
            false
        ),
        (
            'a0000000-0000-0000-0000-000000000003',
            'Standup Facilitator',
            'Guides daily standups and tracks blockers, progress, and plans.',
            'You are a standup facilitator. Help guide the meeting through each participant''s update: what they did yesterday, what they plan today, and any blockers. Track blockers and suggest follow-ups.',
            '["transcription", "task_extraction", "action_items"]'::jsonb,
            'productivity',
            false
        ),
        (
            'a0000000-0000-0000-0000-000000000004',
            'Meeting Summarizer',
            'Generates concise post-meeting summaries with key takeaways.',
            'You are a meeting summarizer. After the meeting, produce a concise summary including: attendees, key discussion topics, decisions made, action items, and next steps. Keep it brief and scannable.',
            '["transcription", "summarization"]'::jsonb,
            'general',
            false
        );
        """
    )


def downgrade() -> None:
    op.drop_table("hosted_agent_sessions")
    op.drop_table("agent_templates")
