"""Create integrations table and add integration_id FK to feeds.

Revision ID: h3c4d5e6f7a8
Revises: h2b3c4d5e6f7
Create Date: 2026-04-06 19:00:00.000000+00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "h3c4d5e6f7a8"
down_revision = "h2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create integrations table and add integration_id to feeds."""
    op.create_table(
        "integrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("external_team_id", sa.String(120), nullable=True),
        sa.Column("external_team_name", sa.String(255), nullable=True),
        sa.Column("bot_user_id", sa.String(120), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_hint", sa.String(8), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
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
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])
    op.create_index(
        "ix_integrations_user_platform",
        "integrations",
        ["user_id", "platform"],
        unique=True,
    )

    op.add_column(
        "feeds",
        sa.Column(
            "integration_id",
            sa.Uuid(),
            sa.ForeignKey("integrations.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_feeds_integration_id", "feeds", ["integration_id"])


def downgrade() -> None:
    """Remove integrations table and integration_id from feeds."""
    op.drop_index("ix_feeds_integration_id", table_name="feeds")
    op.drop_column("feeds", "integration_id")
    op.drop_index("ix_integrations_user_platform", table_name="integrations")
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
