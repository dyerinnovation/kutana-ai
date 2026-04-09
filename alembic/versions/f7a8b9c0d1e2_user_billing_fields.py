"""Add billing and subscription fields to users table.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-04-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str = "e6f7a8b9c0d1"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

plan_tier_enum = sa.Enum(
    "basic", "pro", "business", "enterprise", name="plan_tier", create_constraint=True
)

subscription_status_enum = sa.Enum(
    "active",
    "past_due",
    "canceled",
    "trialing",
    "incomplete",
    name="subscription_status",
    create_constraint=True,
)


def upgrade() -> None:
    plan_tier_enum.create(op.get_bind(), checkfirst=True)
    subscription_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "plan_tier",
            plan_tier_enum,
            nullable=False,
            server_default="basic",
        ),
    )
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True, unique=True),
    )
    op.add_column(
        "users",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_status",
            subscription_status_enum,
            nullable=False,
            server_default="trialing",
        ),
    )
    op.add_column(
        "users",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("subscription_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("meetings_this_month", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("billing_cycle_start", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "billing_cycle_start")
    op.drop_column("users", "meetings_this_month")
    op.drop_column("users", "subscription_period_end")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "subscription_status")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "plan_tier")

    subscription_status_enum.drop(op.get_bind(), checkfirst=True)
    plan_tier_enum.drop(op.get_bind(), checkfirst=True)
