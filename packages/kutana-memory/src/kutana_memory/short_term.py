"""Short-term memory layer backed by PostgreSQL via SQLAlchemy async.

Provides queries for recent meetings and tasks, enabling the agent
to recall context from the immediate past.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    String,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class _Base(DeclarativeBase):
    """Declarative base for short-term memory ORM models."""


class MeetingRecord(_Base):
    """ORM model for persisted meeting records used in short-term memory.

    This is a read model -- the authoritative write model lives in
    the service that owns the meetings table. This model is used
    only for querying recent meetings.
    """

    __tablename__ = "meetings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    platform: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class MeetingParticipantLink(_Base):
    """Join table linking meetings to participants for lookup queries."""

    __tablename__ = "meeting_participants"

    meeting_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    participant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)


class TaskRecord(_Base):
    """ORM model for persisted task records used in short-term memory."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    description: Mapped[str] = mapped_column(Text)
    assignee_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50))
    priority: Mapped[str] = mapped_column(String(50))
    source_utterance: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class ShortTermMemory:
    """PostgreSQL-backed short-term memory for recent meeting recall.

    Provides queries to retrieve recent meetings by participant and
    recent tasks by meeting, giving the agent context about what
    has happened in the recent past.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize short-term memory with a SQLAlchemy session factory.

        Args:
            session_factory: An async session factory for database access.
        """
        self._session_factory = session_factory

    async def get_recent_meetings(
        self,
        participant_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieve recent meetings for a participant.

        Queries the meetings table joined through the participant
        link table, ordered by most recent first.

        Args:
            participant_id: UUID of the participant to look up.
            limit: Maximum number of meetings to return.

        Returns:
            List of meeting dictionaries with id, title, platform,
            status, started_at, and ended_at fields.
        """
        async with self._session_factory() as session:
            stmt = (
                select(MeetingRecord)
                .join(
                    MeetingParticipantLink,
                    MeetingRecord.id == MeetingParticipantLink.meeting_id,
                )
                .where(MeetingParticipantLink.participant_id == participant_id)
                .order_by(MeetingRecord.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            meetings = result.scalars().all()

            return [
                {
                    "id": str(m.id),
                    "title": m.title,
                    "platform": m.platform,
                    "status": m.status,
                    "started_at": (m.started_at.isoformat() if m.started_at else None),
                    "ended_at": (m.ended_at.isoformat() if m.ended_at else None),
                }
                for m in meetings
            ]

    async def get_recent_tasks(
        self,
        meeting_id: UUID,
    ) -> list[dict[str, Any]]:
        """Retrieve tasks associated with a specific meeting.

        Args:
            meeting_id: UUID of the meeting to look up tasks for.

        Returns:
            List of task dictionaries with id, description, status,
            priority, assignee_id, and source_utterance fields.
        """
        async with self._session_factory() as session:
            stmt = (
                select(TaskRecord)
                .where(TaskRecord.meeting_id == meeting_id)
                .order_by(TaskRecord.created_at.desc())
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()

            return [
                {
                    "id": str(t.id),
                    "meeting_id": str(t.meeting_id),
                    "description": t.description,
                    "status": t.status,
                    "priority": t.priority,
                    "assignee_id": (str(t.assignee_id) if t.assignee_id else None),
                    "source_utterance": t.source_utterance,
                }
                for t in tasks
            ]
