"""agent gateway models

Revision ID: a1b2c3d4e5f6
Revises: ddd60b812f8a
Create Date: 2026-03-01 12:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "ddd60b812f8a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rooms, agent_sessions tables; alter meetings, participants, agent_configs."""
    # --- New tables ---
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("meeting_id", sa.Uuid, sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("livekit_room_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("max_participants", sa.Integer, nullable=False, server_default="0"),
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
    op.create_index("ix_rooms_status", "rooms", ["status"])
    op.create_index("ix_rooms_meeting_id", "rooms", ["meeting_id"])

    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "agent_config_id",
            sa.Uuid,
            sa.ForeignKey("agent_configs.id"),
            nullable=False,
        ),
        sa.Column("meeting_id", sa.Uuid, sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("room_name", sa.String(255), nullable=True),
        sa.Column(
            "connection_type",
            sa.String(50),
            nullable=False,
            server_default="agent_gateway",
        ),
        sa.Column("capabilities", JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="connecting"),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_agent_sessions_meeting_id", "agent_sessions", ["meeting_id"])
    op.create_index("ix_agent_sessions_agent_config_id", "agent_sessions", ["agent_config_id"])
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"])

    # --- Alter meetings table ---
    # Make dial_in_number and meeting_code nullable
    op.alter_column("meetings", "dial_in_number", existing_type=sa.String(50), nullable=True)
    op.alter_column("meetings", "meeting_code", existing_type=sa.String(100), nullable=True)
    # Add new columns
    op.add_column("meetings", sa.Column("room_id", sa.Uuid, nullable=True))
    op.add_column("meetings", sa.Column("room_name", sa.String(255), nullable=True))
    op.add_column(
        "meetings",
        sa.Column("meeting_type", sa.String(50), nullable=False, server_default="standard"),
    )

    # --- Alter participants table ---
    op.add_column("participants", sa.Column("connection_type", sa.String(50), nullable=True))
    op.add_column(
        "participants",
        sa.Column(
            "agent_config_id",
            sa.Uuid,
            sa.ForeignKey("agent_configs.id"),
            nullable=True,
        ),
    )

    # --- Alter agent_configs table ---
    op.add_column(
        "agent_configs",
        sa.Column("agent_type", sa.String(50), nullable=False, server_default="custom"),
    )
    op.add_column(
        "agent_configs",
        sa.Column("protocol_version", sa.String(10), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "agent_configs",
        sa.Column("default_capabilities", JSONB, nullable=True),
    )
    op.add_column(
        "agent_configs",
        sa.Column("max_concurrent_sessions", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    """Reverse agent gateway model changes."""
    # --- Revert agent_configs ---
    op.drop_column("agent_configs", "max_concurrent_sessions")
    op.drop_column("agent_configs", "default_capabilities")
    op.drop_column("agent_configs", "protocol_version")
    op.drop_column("agent_configs", "agent_type")

    # --- Revert participants ---
    op.drop_column("participants", "agent_config_id")
    op.drop_column("participants", "connection_type")

    # --- Revert meetings ---
    op.drop_column("meetings", "meeting_type")
    op.drop_column("meetings", "room_name")
    op.drop_column("meetings", "room_id")
    op.alter_column("meetings", "meeting_code", existing_type=sa.String(100), nullable=False)
    op.alter_column("meetings", "dial_in_number", existing_type=sa.String(50), nullable=False)

    # --- Drop new tables ---
    op.drop_index("ix_agent_sessions_status", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_agent_config_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_meeting_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")

    op.drop_index("ix_rooms_meeting_id", table_name="rooms")
    op.drop_index("ix_rooms_status", table_name="rooms")
    op.drop_table("rooms")
