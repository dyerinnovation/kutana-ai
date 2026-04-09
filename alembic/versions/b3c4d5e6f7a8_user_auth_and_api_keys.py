"""User auth and API keys.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b3c4d5e6f7a8"
down_revision: str = "a1b2c3d4e5f6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create users and agent_api_keys tables, add owner_id to agent_configs."""
    # --- users table ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- owner_id on agent_configs ---
    op.add_column(
        "agent_configs",
        sa.Column("owner_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_configs_owner_id",
        "agent_configs",
        "users",
        ["owner_id"],
        ["id"],
    )
    op.create_index("ix_agent_configs_owner_id", "agent_configs", ["owner_id"])

    # --- agent_api_keys table ---
    op.create_table(
        "agent_api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("agent_config_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default="default"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_config_id"], ["agent_configs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_agent_api_keys_key_hash", "agent_api_keys", ["key_hash"], unique=True)
    op.create_index("ix_agent_api_keys_agent_config_id", "agent_api_keys", ["agent_config_id"])
    op.create_index("ix_agent_api_keys_user_id", "agent_api_keys", ["user_id"])


def downgrade() -> None:
    """Drop agent_api_keys, remove owner_id from agent_configs, drop users."""
    op.drop_table("agent_api_keys")
    op.drop_index("ix_agent_configs_owner_id", table_name="agent_configs")
    op.drop_constraint("fk_agent_configs_owner_id", "agent_configs", type_="foreignkey")
    op.drop_column("agent_configs", "owner_id")
    op.drop_table("users")
