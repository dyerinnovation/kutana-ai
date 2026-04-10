"""Feed domain models for the Kutana Feeds integration layer."""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003 — Pydantic needs runtime access for field types
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FeedDirection(enum.StrEnum):
    """Direction of data flow for a feed."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class FeedBase(BaseModel):
    """Shared fields for feed create/update/read schemas.

    Attributes:
        name: Human-readable feed name.
        platform: Target platform identifier.
        direction: Data flow direction.
        delivery_type: Delivery mechanism — MCP server or channel plugin.
        mcp_server_url: MCP server URL (required when delivery_type == "mcp").
        channel_name: Channel plugin name (required when delivery_type == "channel").
        data_types: What to push outbound.
        context_types: What to pull inbound.
        trigger: When to fire the feed.
        meeting_tag: Optional tag filter.
    """

    name: str
    platform: str
    direction: Literal["inbound", "outbound", "bidirectional"] = "outbound"
    delivery_type: Literal["mcp", "channel"]
    mcp_server_url: str | None = None
    channel_name: str | None = None
    data_types: list[Literal["summary", "transcript", "tasks", "decisions"]] = Field(
        default_factory=list
    )
    context_types: list[Literal["thread", "page", "issue", "document"]] = Field(
        default_factory=list
    )
    trigger: Literal["meeting_ended", "participant_left", "meeting_started", "manual"] = (
        "meeting_ended"
    )
    meeting_tag: str | None = None


class FeedCreate(FeedBase):
    """Request body for creating a new feed.

    Attributes:
        mcp_auth_token: Write-only MCP auth token. Never returned in responses.
            Encrypted before persistence.
        integration_id: Optional OAuth integration UUID. When set, the feed
            uses the integration's token instead of mcp_auth_token.
    """

    mcp_auth_token: str | None = None
    integration_id: str | None = None


class FeedUpdate(BaseModel):
    """Request body for updating an existing feed.

    All fields are optional — only provided fields are updated.

    Attributes:
        name: Updated feed name.
        platform: Updated platform.
        direction: Updated direction.
        delivery_type: Updated delivery mechanism.
        mcp_server_url: Updated MCP server URL.
        channel_name: Updated channel name.
        data_types: Updated outbound data types.
        context_types: Updated inbound context types.
        trigger: Updated trigger.
        meeting_tag: Updated tag filter.
        is_active: Enable or disable the feed.
        mcp_auth_token: Write-only — update the encrypted token.
    """

    name: str | None = None
    platform: str | None = None
    direction: Literal["inbound", "outbound", "bidirectional"] | None = None
    delivery_type: Literal["mcp", "channel"] | None = None
    mcp_server_url: str | None = None
    channel_name: str | None = None
    data_types: list[Literal["summary", "transcript", "tasks", "decisions"]] | None = None
    context_types: list[Literal["thread", "page", "issue", "document"]] | None = None
    trigger: Literal["meeting_ended", "participant_left", "meeting_started", "manual"] | None = None
    meeting_tag: str | None = None
    is_active: bool | None = None
    mcp_auth_token: str | None = None


class FeedRead(FeedBase):
    """Response model for a feed.

    Attributes:
        id: Feed UUID.
        user_id: Owner UUID.
        is_active: Whether the feed is enabled.
        created_at: When the feed was created.
        last_triggered_at: Last successful trigger time.
        last_error: Most recent error message.
        token_hint: Last 4 chars of stored auth token (from feed_secrets).
    """

    id: UUID
    user_id: UUID
    is_active: bool
    integration_id: str | None = None
    created_at: datetime
    last_triggered_at: datetime | None = None
    last_error: str | None = None
    token_hint: str | None = None


class FeedRunRead(BaseModel):
    """Response model for a feed run.

    Attributes:
        id: Run UUID.
        feed_id: Parent feed UUID.
        meeting_id: Meeting this run was triggered for.
        trigger: What triggered this run.
        direction: Run direction.
        status: Current run status.
        agent_session_id: Agent session identifier.
        started_at: When the run started.
        finished_at: When the run finished.
        error: Error message if failed.
    """

    id: UUID = Field(default_factory=uuid4)
    feed_id: UUID
    meeting_id: UUID
    trigger: str
    direction: str
    status: str
    agent_session_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
