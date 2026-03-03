"""Agent session domain model."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ConnectionType(enum.StrEnum):
    """How a participant connects to a meeting."""

    WEBRTC = "webrtc"
    AGENT_GATEWAY = "agent_gateway"
    PHONE = "phone"


class AgentSessionStatus(enum.StrEnum):
    """Status of an agent session."""

    CONNECTING = "connecting"
    ACTIVE = "active"
    DISCONNECTED = "disconnected"


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class AgentSession(BaseModel):
    """Represents an active agent connection to a meeting.

    Attributes:
        id: Unique session identifier.
        agent_config_id: ID of the agent configuration.
        meeting_id: ID of the meeting the agent joined.
        room_name: Name of the room the agent is in.
        connection_type: How the agent is connected.
        capabilities: List of granted capabilities for this session.
        status: Current session status.
        connected_at: When the agent connected.
        disconnected_at: When the agent disconnected.
        created_at: When this record was created.
    """

    id: UUID = Field(default_factory=uuid4)
    agent_config_id: UUID
    meeting_id: UUID
    room_name: str | None = None
    connection_type: ConnectionType = ConnectionType.AGENT_GATEWAY
    capabilities: list[str] = Field(default_factory=list)
    status: AgentSessionStatus = AgentSessionStatus.CONNECTING
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utc_now)
