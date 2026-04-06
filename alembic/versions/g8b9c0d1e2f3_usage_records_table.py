"""Add usage_records table for time-based metering.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-04-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "g8b9c0d1e2f3"
down_revision: str = "f7a8b9c0d1e2"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billing_period", sa.String(7), nullable=False),
    )
    op.create_index(
        "ix_usage_records_user_period",
        "usage_records",
        ["user_id", "billing_period"],
    )
    op.create_index(
        "ix_usage_records_resource",
        "usage_records",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_records_resource", table_name="usage_records")
    op.drop_index("ix_usage_records_user_period", table_name="usage_records")
    op.drop_table("usage_records")
