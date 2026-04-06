"""SQLAlchemy 2.0 ORM models for Kutana AI."""

from __future__ import annotations

from datetime import date, datetime  # noqa: TC003
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kutana_core.database.base import Base


class MeetingORM(Base):
    """ORM model for meetings table.

    Attributes:
        id: Primary key UUID.
        platform: Meeting platform identifier.
        dial_in_number: Phone number to dial into the meeting (optional, legacy).
        meeting_code: Access code for the meeting (optional, legacy).
        title: Optional human-readable meeting title.
        room_id: Associated room UUID.
        room_name: Room name for easy lookup.
        meeting_type: Type of meeting.
        scheduled_at: Scheduled start time.
        started_at: Actual start time.
        ended_at: Actual end time.
        status: Current meeting status.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
    """

    __tablename__ = "meetings"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    dial_in_number: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    meeting_code: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    room_id: Mapped[UUID | None] = mapped_column(sa.Uuid, nullable=True)
    room_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    meeting_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, default="standard")
    scheduled_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    tasks: Mapped[list[TaskORM]] = relationship(back_populates="meeting", lazy="selectin")
    decisions: Mapped[list[DecisionORM]] = relationship(back_populates="meeting", lazy="selectin")
    transcript_segments: Mapped[list[TranscriptSegmentORM]] = relationship(
        back_populates="meeting", lazy="selectin"
    )

    __table_args__ = (Index("ix_meetings_status", "status"),)


class ParticipantORM(Base):
    """ORM model for participants table.

    Attributes:
        id: Primary key UUID.
        name: Display name of the participant.
        email: Optional email address.
        speaker_id: Speaker identifier from diarization.
        role: Participant role in the meeting.
        connection_type: How the participant is connected.
        agent_config_id: Associated agent config (for agent participants).
        created_at: Record creation timestamp.
    """

    __tablename__ = "participants"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="participant")
    connection_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    agent_config_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid, ForeignKey("agent_configs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class TaskORM(Base):
    """ORM model for tasks table.

    Attributes:
        id: Primary key UUID.
        meeting_id: Foreign key to meetings table.
        description: Task description.
        assignee_id: Foreign key to participants table.
        due_date: Optional due date.
        priority: Task priority level.
        status: Current task status.
        dependencies: JSON array of dependent task UUIDs.
        source_utterance: Original transcript text.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("meetings.id"), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    assignee_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid, ForeignKey("participants.id"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    priority: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending")
    dependencies: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    source_utterance: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    meeting: Mapped[MeetingORM] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_meeting_id", "meeting_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_assignee_id", "assignee_id"),
    )


class DecisionORM(Base):
    """ORM model for decisions table.

    Attributes:
        id: Primary key UUID.
        meeting_id: Foreign key to meetings table.
        description: Decision description.
        decided_by_id: Foreign key to participants table.
        participants_present: JSON array of participant UUIDs.
        created_at: Record creation timestamp.
    """

    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("meetings.id"), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    decided_by_id: Mapped[UUID] = mapped_column(
        sa.Uuid, ForeignKey("participants.id"), nullable=False
    )
    participants_present: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    meeting: Mapped[MeetingORM] = relationship(back_populates="decisions")

    __table_args__ = (Index("ix_decisions_meeting_id", "meeting_id"),)


class TranscriptSegmentORM(Base):
    """ORM model for transcript_segments table.

    Attributes:
        id: Primary key UUID.
        meeting_id: Foreign key to meetings table.
        speaker_id: Speaker identifier from diarization.
        text: Transcribed text content.
        start_time: Segment start time in seconds.
        end_time: Segment end time in seconds.
        confidence: STT confidence score.
        created_at: Record creation timestamp.
    """

    __tablename__ = "transcript_segments"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("meetings.id"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    start_time: Mapped[float] = mapped_column(sa.Float, nullable=False)
    end_time: Mapped[float] = mapped_column(sa.Float, nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    meeting: Mapped[MeetingORM] = relationship(back_populates="transcript_segments")

    __table_args__ = (Index("ix_transcript_segments_meeting_id", "meeting_id"),)


class UserORM(Base):
    """ORM model for users table.

    Attributes:
        id: Primary key UUID.
        email: Unique email address.
        hashed_password: Bcrypt-hashed password.
        name: Display name.
        is_active: Whether the account is active.
        plan_tier: Subscription tier (basic, pro, business, enterprise).
        stripe_customer_id: Stripe customer ID.
        stripe_subscription_id: Stripe subscription ID.
        subscription_status: Current subscription state.
        trial_ends_at: When the free trial expires.
        subscription_period_end: Current billing period end.
        meetings_this_month: Meeting count for current billing cycle.
        billing_cycle_start: Start of current billing cycle.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    avatar_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)

    # Billing & subscription
    plan_tier: Mapped[str] = mapped_column(
        sa.Enum("basic", "pro", "business", "enterprise", name="plan_tier"),
        nullable=False,
        server_default="basic",
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True, unique=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        sa.String(255), nullable=True
    )
    subscription_status: Mapped[str] = mapped_column(
        sa.Enum(
            "active", "past_due", "canceled", "trialing", "incomplete",
            name="subscription_status",
        ),
        nullable=False,
        server_default="trialing",
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    subscription_period_end: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    meetings_this_month: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )
    billing_cycle_start: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (Index("ix_users_email", "email", unique=True),)


class AgentConfigORM(Base):
    """ORM model for agent_configs table.

    Attributes:
        id: Primary key UUID.
        name: Agent name.
        voice_id: TTS voice identifier.
        system_prompt: System prompt for the agent.
        capabilities: JSON array of capability strings.
        meeting_type_filter: JSON array of meeting type strings.
        agent_type: Type of agent (custom, livekit, etc.).
        protocol_version: Protocol version the agent supports.
        default_capabilities: Default capabilities for the agent.
        max_concurrent_sessions: Max concurrent sessions allowed.
        owner_id: FK to users table (nullable for backward compat).
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
    """

    __tablename__ = "agent_configs"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    voice_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    capabilities: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    meeting_type_filter: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=list
    )
    agent_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, default="custom")
    protocol_version: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="1.0")
    default_capabilities: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=list
    )
    max_concurrent_sessions: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    owner_id: Mapped[UUID | None] = mapped_column(sa.Uuid, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (Index("ix_agent_configs_owner_id", "owner_id"),)


class AgentApiKeyORM(Base):
    """ORM model for agent_api_keys table.

    Attributes:
        id: Primary key UUID.
        key_prefix: First 8 chars of the raw key (for display).
        key_hash: SHA-256 hash of the full raw key (for lookup).
        agent_config_id: FK to agent_configs table.
        user_id: FK to users table.
        name: Human-readable key name.
        expires_at: When the key expires (null = never).
        revoked_at: When the key was revoked (null = active).
        created_at: Record creation timestamp.
    """

    __tablename__ = "agent_api_keys"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    key_prefix: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    key_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    agent_config_id: Mapped[UUID] = mapped_column(
        sa.Uuid, ForeignKey("agent_configs.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, default="default")
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        Index("ix_agent_api_keys_key_hash", "key_hash", unique=True),
        Index("ix_agent_api_keys_agent_config_id", "agent_config_id"),
        Index("ix_agent_api_keys_user_id", "user_id"),
    )


class ApiKeyAuditLogORM(Base):
    """ORM model for api_key_audit_log table.

    Attributes:
        id: Primary key UUID.
        key_id: FK to agent_api_keys table.
        action: What happened (created, used, revoked).
        ip_address: Client IP address.
        user_agent: Client User-Agent header.
        created_at: When the event occurred.
    """

    __tablename__ = "api_key_audit_log"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    key_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("agent_api_keys.id"), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        Index("ix_api_key_audit_log_key_id", "key_id"),
        Index("ix_api_key_audit_log_action", "action"),
    )


class RoomORM(Base):
    """ORM model for rooms table.

    Attributes:
        id: Primary key UUID.
        name: Unique human-readable room name.
        meeting_id: Associated meeting ID.
        livekit_room_id: LiveKit room identifier.
        status: Current room status.
        max_participants: Maximum participants (0 = unlimited).
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
    """

    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    meeting_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid, ForeignKey("meetings.id"), nullable=True
    )
    livekit_room_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending")
    max_participants: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        Index("ix_rooms_status", "status"),
        Index("ix_rooms_meeting_id", "meeting_id"),
    )


class AgentSessionORM(Base):
    """ORM model for agent_sessions table.

    Attributes:
        id: Primary key UUID.
        agent_config_id: Associated agent configuration.
        meeting_id: Meeting the agent joined.
        room_name: Room name.
        connection_type: How the agent connected.
        capabilities: Granted capabilities for this session.
        status: Session status.
        connected_at: When the agent connected.
        disconnected_at: When the agent disconnected.
        created_at: Record creation timestamp.
    """

    __tablename__ = "agent_sessions"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    agent_config_id: Mapped[UUID] = mapped_column(
        sa.Uuid, ForeignKey("agent_configs.id"), nullable=False
    )
    meeting_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("meetings.id"), nullable=False)
    room_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    connection_type: Mapped[str] = mapped_column(
        sa.String(50), nullable=False, default="agent_gateway"
    )
    capabilities: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="connecting")
    connected_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        Index("ix_agent_sessions_meeting_id", "meeting_id"),
        Index("ix_agent_sessions_agent_config_id", "agent_config_id"),
        Index("ix_agent_sessions_status", "status"),
    )


class AgentTemplateORM(Base):
    """ORM model for agent_templates table.

    Attributes:
        id: Primary key UUID.
        name: Template display name.
        description: What the template does.
        system_prompt: Default system prompt.
        capabilities: Default capabilities.
        category: Template category for filtering.
        is_premium: Whether this is a premium template.
        created_at: Record creation timestamp.
    """

    __tablename__ = "agent_templates"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    capabilities: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    category: Mapped[str] = mapped_column(sa.String(50), nullable=False, default="general")
    is_premium: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (Index("ix_agent_templates_category", "category"),)


class HostedAgentSessionORM(Base):
    """ORM model for hosted_agent_sessions table.

    Attributes:
        id: Primary key UUID.
        user_id: User who activated the template.
        template_id: Template being used.
        meeting_id: Meeting the hosted agent is in.
        status: Session status (active, stopped).
        anthropic_api_key_encrypted: Encrypted API key (optional).
        started_at: When the session started.
        ended_at: When the session ended.
        created_at: Record creation timestamp.
    """

    __tablename__ = "hosted_agent_sessions"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("users.id"), nullable=False)
    template_id: Mapped[UUID] = mapped_column(
        sa.Uuid, ForeignKey("agent_templates.id"), nullable=False
    )
    meeting_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("meetings.id"), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="active")
    anthropic_api_key_encrypted: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        Index("ix_hosted_agent_sessions_user_id", "user_id"),
        Index("ix_hosted_agent_sessions_meeting_id", "meeting_id"),
        Index("ix_hosted_agent_sessions_status", "status"),
    )


# ---------------------------------------------------------------------------
# Feed models (Kutana Feeds — bidirectional integration layer)
# ---------------------------------------------------------------------------


class FeedORM(Base):
    """ORM model for feeds table.

    Attributes:
        id: Primary key UUID.
        user_id: Owner of this feed configuration.
        name: Human-readable feed name.
        is_active: Whether the feed is enabled.
        platform: Target platform (slack, discord, notion, etc.).
        delivery_type: How to deliver — "mcp" or "channel".
        mcp_server_url: MCP server URL (for delivery_type == "mcp").
        channel_name: Channel plugin name (for delivery_type == "channel").
        direction: "inbound", "outbound", or "bidirectional".
        data_types: What to push outbound (summary, transcript, tasks, decisions).
        context_types: What to pull inbound (thread, page, issue, document).
        trigger: When to fire (meeting_ended, meeting_started, participant_left, manual).
        meeting_tag: Optional tag filter — null means all meetings.
        created_at: Record creation timestamp.
        updated_at: Record update timestamp.
        last_triggered_at: Last successful trigger time.
        last_error: Most recent error message.
    """

    __tablename__ = "feeds"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    platform: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    delivery_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    mcp_server_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    channel_name: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    direction: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="outbound")
    data_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    context_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    trigger: Mapped[str] = mapped_column(sa.String(40), nullable=False, default="meeting_ended")
    meeting_tag: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    runs: Mapped[list[FeedRunORM]] = relationship(back_populates="feed", lazy="selectin")
    secret: Mapped[FeedSecretORM | None] = relationship(
        back_populates="feed", uselist=False, lazy="selectin"
    )

    __table_args__ = (
        Index("ix_feeds_user_id", "user_id"),
        Index("ix_feeds_is_active", "is_active"),
    )


class FeedRunORM(Base):
    """ORM model for feed_runs table.

    Tracks every feed delivery attempt for observability and retry.

    Attributes:
        id: Primary key UUID.
        feed_id: Foreign key to feeds table.
        meeting_id: Foreign key to meetings table.
        trigger: What triggered this run.
        direction: "inbound" or "outbound".
        status: "pending", "running", "delivered", or "failed".
        agent_session_id: Identifier for the agent session running this feed.
        started_at: When the run started.
        finished_at: When the run finished.
        error: Error message if the run failed.
    """

    __tablename__ = "feed_runs"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    feed_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("feeds.id"), nullable=False)
    meeting_id: Mapped[UUID] = mapped_column(sa.Uuid, ForeignKey("meetings.id"), nullable=False)
    trigger: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    direction: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="pending")
    agent_session_id: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    feed: Mapped[FeedORM] = relationship(back_populates="runs")

    __table_args__ = (
        Index("ix_feed_runs_feed_id", "feed_id"),
        Index("ix_feed_runs_meeting_id", "meeting_id"),
        Index("ix_feed_runs_status", "status"),
    )


class MeetingSummaryORM(Base):
    """ORM model for meeting_summaries table.

    Caches generated meeting summaries to avoid redundant LLM calls.

    Attributes:
        id: Primary key UUID.
        meeting_id: Foreign key to meetings table (unique).
        key_points: JSON array of key discussion points.
        decisions: JSON array of recorded decisions.
        task_count: Number of tasks extracted.
        generated_at: When the summary was generated.
        model_used: LLM model identifier used for generation.
    """

    __tablename__ = "meeting_summaries"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(
        sa.Uuid, ForeignKey("meetings.id"), nullable=False, unique=True
    )
    key_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    decisions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    task_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    generated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    model_used: Mapped[str] = mapped_column(sa.String(60), nullable=False)

    __table_args__ = (Index("ix_meeting_summaries_meeting_id", "meeting_id", unique=True),)


class FeedSecretORM(Base):
    """ORM model for feed_secrets table.

    Stores encrypted MCP auth tokens separately from feed config.
    Tokens are AES-256-GCM encrypted and never returned via API.

    Attributes:
        id: Primary key UUID.
        feed_id: Foreign key to feeds table (unique).
        encrypted_token: AES-256-GCM ciphertext of the auth token.
        token_hint: Last 4 characters of the plaintext token for UI display.
        created_at: Record creation timestamp.
        rotated_at: When the token was last rotated.
    """

    __tablename__ = "feed_secrets"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid4)
    feed_id: Mapped[UUID] = mapped_column(
        sa.Uuid, ForeignKey("feeds.id"), nullable=False, unique=True
    )
    encrypted_token: Mapped[str] = mapped_column(sa.Text, nullable=False)
    token_hint: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    rotated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    feed: Mapped[FeedORM] = relationship(back_populates="secret")

    __table_args__ = (Index("ix_feed_secrets_feed_id", "feed_id", unique=True),)
