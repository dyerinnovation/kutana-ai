"""Add avatar_url to users table.

Revision ID: a0b1c2d3e4f5
Revises: f7a8b9c0d1e2
Create Date: 2026-04-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str = "f7a8b9c0d1e2"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
