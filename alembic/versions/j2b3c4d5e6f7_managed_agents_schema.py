"""Add managed agents schema: tier column, anthropic session fields, org SOPs, new templates.

Revision ID: j2b3c4d5e6f7
Revises: i1a2b3c4d5e6
Create Date: 2026-04-09
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "j2b3c4d5e6f7"
down_revision: str | None = "i1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None  # type: ignore[type-arg] — Alembic convention
depends_on: str | Sequence[str] | None = None  # type: ignore[type-arg] — Alembic convention


def upgrade() -> None:
    # --- AgentTemplateORM: add tier column ---
    op.add_column(
        "agent_templates",
        sa.Column("tier", sa.String(20), nullable=False, server_default="basic"),
    )

    # --- HostedAgentSessionORM: add Anthropic session tracking ---
    op.add_column(
        "hosted_agent_sessions",
        sa.Column("anthropic_session_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "hosted_agent_sessions",
        sa.Column("anthropic_agent_id", sa.String(255), nullable=True),
    )

    # --- OrganizationSOP table ---
    op.create_table(
        "organization_sops",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organization_sops_org_id", "organization_sops", ["organization_id"])
    op.create_index(
        "ix_organization_sops_category",
        "organization_sops",
        ["organization_id", "category"],
    )

    # --- Rename "Technical Scribe" → "Code Discussion Tracker" ---
    op.execute(
        """
        UPDATE agent_templates
        SET name = 'Code Discussion Tracker'
        WHERE id = 'a0000000-0000-0000-0000-000000000002'
        """
    )

    # --- Set tier values on existing templates ---
    # basic: Notetaker (001), Summarizer (004)
    op.execute(
        """
        UPDATE agent_templates SET tier = 'basic'
        WHERE id IN (
            'a0000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000004'
        )
        """
    )
    # pro: Code Discussion Tracker (002), Standup Facilitator (003)
    op.execute(
        """
        UPDATE agent_templates SET tier = 'pro', is_premium = true
        WHERE id IN (
            'a0000000-0000-0000-0000-000000000002',
            'a0000000-0000-0000-0000-000000000003'
        )
        """
    )

    # --- Insert 6 new templates ---
    op.execute(
        """
        INSERT INTO agent_templates (id, name, description, system_prompt, capabilities, category, is_premium, tier)
        VALUES
        (
            'a0000000-0000-0000-0000-000000000005',
            'Action Item Tracker',
            'Identifies, assigns, and tracks action items throughout the meeting in real time.',
            'You are an action item tracker. Monitor the conversation for commitments, assignments, and follow-ups. For each action item, capture: the task, the assignee, the deadline (if mentioned), and the context. Present a running list and flag items that lack an owner or deadline.',
            '["task_extraction", "action_items"]'::jsonb,
            'productivity',
            true,
            'pro'
        ),
        (
            'a0000000-0000-0000-0000-000000000006',
            'Decision Logger',
            'Records decisions as they happen, capturing rationale, alternatives considered, and stakeholders involved.',
            'You are a decision logger. When a decision is made in the meeting, capture: the decision itself, who made it, what alternatives were discussed, the rationale for the choice, and any dissenting opinions. Organize by topic.',
            '["transcription", "summarization"]'::jsonb,
            'productivity',
            true,
            'pro'
        ),
        (
            'a0000000-0000-0000-0000-000000000007',
            'Sprint Retro Coach',
            'Facilitates sprint retrospectives using structured frameworks (Start/Stop/Continue, 4Ls, etc.).',
            'You are a sprint retrospective coach. Guide the team through a structured retro using the Start/Stop/Continue framework. Collect feedback in each category, identify patterns, and help the team agree on concrete improvement actions for the next sprint.',
            '["transcription", "task_extraction", "action_items"]'::jsonb,
            'engineering',
            true,
            'business'
        ),
        (
            'a0000000-0000-0000-0000-000000000008',
            'Sprint Planner',
            'Assists with sprint planning by tracking story estimation, capacity, and commitment.',
            'You are a sprint planning assistant. Help the team estimate stories, track capacity, and build the sprint backlog. Summarize each story discussed, capture estimates, flag risks or dependencies, and maintain a running total of committed points vs. capacity.',
            '["transcription", "task_extraction", "summarization"]'::jsonb,
            'engineering',
            true,
            'business'
        ),
        (
            'a0000000-0000-0000-0000-000000000009',
            'User Interviewer',
            'Guides user interviews with structured question frameworks and captures insights.',
            'You are a user interview assistant. Help the interviewer follow a structured interview guide. Capture user quotes verbatim, note emotional reactions, identify pain points and delights, and produce a structured insight summary at the end.',
            '["transcription", "summarization"]'::jsonb,
            'research',
            true,
            'business'
        ),
        (
            'a0000000-0000-0000-0000-00000000000a',
            'Initial Interviewer',
            'Conducts structured initial candidate interviews with consistent scoring and evaluation.',
            'You are an initial interview assistant. Help the interviewer conduct a structured candidate screen. Track responses to each question, note communication quality, capture technical depth indicators, and produce a structured scorecard at the end.',
            '["transcription", "summarization", "action_items"]'::jsonb,
            'hr',
            true,
            'business'
        );
        """
    )


def downgrade() -> None:
    # Remove new templates
    op.execute(
        """
        DELETE FROM agent_templates
        WHERE id IN (
            'a0000000-0000-0000-0000-000000000005',
            'a0000000-0000-0000-0000-000000000006',
            'a0000000-0000-0000-0000-000000000007',
            'a0000000-0000-0000-0000-000000000008',
            'a0000000-0000-0000-0000-000000000009',
            'a0000000-0000-0000-0000-00000000000a'
        )
        """
    )

    # Revert "Code Discussion Tracker" → "Technical Scribe"
    op.execute(
        """
        UPDATE agent_templates
        SET name = 'Technical Scribe'
        WHERE id = 'a0000000-0000-0000-0000-000000000002'
        """
    )

    # Reset tier values on existing templates
    op.execute(
        """
        UPDATE agent_templates SET tier = 'basic', is_premium = false
        WHERE id IN (
            'a0000000-0000-0000-0000-000000000002',
            'a0000000-0000-0000-0000-000000000003'
        )
        """
    )

    # Drop organization_sops
    op.drop_index("ix_organization_sops_category", table_name="organization_sops")
    op.drop_index("ix_organization_sops_org_id", table_name="organization_sops")
    op.drop_table("organization_sops")

    # Drop new columns
    op.drop_column("hosted_agent_sessions", "anthropic_agent_id")
    op.drop_column("hosted_agent_sessions", "anthropic_session_id")
    op.drop_column("agent_templates", "tier")
