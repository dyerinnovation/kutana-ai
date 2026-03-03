"""Agent configuration domain model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class AgentConfig(BaseModel):
    """Configuration for an AI meeting agent.

    Attributes:
        id: Unique agent configuration identifier.
        name: Human-readable name for the agent.
        voice_id: TTS voice identifier for the agent.
        system_prompt: System prompt used when the agent participates.
        capabilities: List of capability strings the agent supports.
        meeting_type_filter: Meeting types this agent should join.
        created_at: When this record was created.
        updated_at: When this record was last updated.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    voice_id: str | None = None
    system_prompt: str
    capabilities: list[str] = Field(default_factory=list)
    meeting_type_filter: list[str] = Field(default_factory=list)
    agent_type: str = "custom"
    protocol_version: str = "1.0"
    default_capabilities: list[str] = Field(default_factory=list)
    max_concurrent_sessions: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
