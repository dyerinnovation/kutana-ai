"""Add expires_at to agent_api_keys and create api_key_audit_log table.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str = "b3c4d5e6f7a8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add expires_at column and create audit log table."""
    # --- Add expires_at to agent_api_keys ---
    op.add_column(
        "agent_api_keys",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- api_key_audit_log table ---
    op.create_table(
        "api_key_audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_id"], ["agent_api_keys.id"]),
    )
    op.create_index(
        "ix_api_key_audit_log_key_id", "api_key_audit_log", ["key_id"]
    )
    op.create_index(
        "ix_api_key_audit_log_action", "api_key_audit_log", ["action"]
    )


def downgrade() -> None:
    """Remove audit log table and expires_at column."""
    op.drop_table("api_key_audit_log")
    op.drop_column("agent_api_keys", "expires_at")
