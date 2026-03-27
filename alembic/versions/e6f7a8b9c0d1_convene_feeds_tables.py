"""Create feeds, feed_runs, meeting_summaries, and feed_secrets tables.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-26
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- feeds ---
    op.create_table(
        "feeds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("delivery_type", sa.String(20), nullable=False),
        sa.Column("mcp_server_url", sa.Text(), nullable=True),
        sa.Column("channel_name", sa.String(80), nullable=True),
        sa.Column("direction", sa.String(20), nullable=False, server_default="outbound"),
        sa.Column("data_types", JSONB(), nullable=False, server_default="[]"),
        sa.Column("context_types", JSONB(), nullable=False, server_default="[]"),
        sa.Column("trigger", sa.String(40), nullable=False, server_default="meeting_ended"),
        sa.Column("meeting_tag", sa.String(80), nullable=True),
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
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_feeds_user_id", "feeds", ["user_id"])
    op.create_index("ix_feeds_is_active", "feeds", ["is_active"])

    # --- feed_runs ---
    op.create_table(
        "feed_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.String(40), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("agent_session_id", sa.String(80), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"]),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
    )
    op.create_index("ix_feed_runs_feed_id", "feed_runs", ["feed_id"])
    op.create_index("ix_feed_runs_meeting_id", "feed_runs", ["meeting_id"])
    op.create_index("ix_feed_runs_status", "feed_runs", ["status"])

    # --- meeting_summaries ---
    op.create_table(
        "meeting_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("key_points", JSONB(), nullable=False),
        sa.Column("decisions", JSONB(), nullable=False),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("model_used", sa.String(60), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.UniqueConstraint("meeting_id"),
    )
    op.create_index(
        "ix_meeting_summaries_meeting_id", "meeting_summaries", ["meeting_id"], unique=True
    )

    # --- feed_secrets ---
    op.create_table(
        "feed_secrets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("token_hint", sa.String(8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["feed_id"], ["feeds.id"]),
        sa.UniqueConstraint("feed_id"),
    )
    op.create_index("ix_feed_secrets_feed_id", "feed_secrets", ["feed_id"], unique=True)


def downgrade() -> None:
    op.drop_table("feed_secrets")
    op.drop_table("meeting_summaries")
    op.drop_table("feed_runs")
    op.drop_table("feeds")
