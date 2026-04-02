"""Structured memory layer for indexed task and decision queries.

Provides direct database queries for tasks and decisions with
filtering by assignee, meeting, and dependency relationships.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    String,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from kutana_core.models.decision import Decision
from kutana_core.models.task import Task, TaskPriority, TaskStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class _Base(DeclarativeBase):
    """Declarative base for structured memory ORM models."""


class TaskRow(_Base):
    """ORM model for tasks in structured memory.

    Maps directly to the tasks table and is used for indexed
    queries on status, assignee, and dependencies.
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    dependencies: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    source_utterance: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class DecisionRow(_Base):
    """ORM model for decisions in structured memory."""

    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    meeting_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    participants_present: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


def _task_row_to_model(row: TaskRow) -> Task:
    """Convert a TaskRow ORM instance to a Task domain model.

    Args:
        row: The SQLAlchemy ORM row.

    Returns:
        A Task Pydantic model instance.
    """
    dep_uuids: list[UUID] = []
    for dep_str in row.dependencies:
        try:
            dep_uuids.append(UUID(dep_str))
        except ValueError:
            logger.warning("Invalid dependency UUID: %s", dep_str)

    return Task(
        id=row.id,
        meeting_id=row.meeting_id,
        description=row.description,
        assignee_id=row.assignee_id,
        due_date=(row.due_date.date() if row.due_date else None),
        priority=TaskPriority(row.priority),
        status=TaskStatus(row.status),
        dependencies=dep_uuids,
        source_utterance=row.source_utterance,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _decision_row_to_model(row: DecisionRow) -> Decision:
    """Convert a DecisionRow ORM instance to a Decision domain model.

    Args:
        row: The SQLAlchemy ORM row.

    Returns:
        A Decision Pydantic model instance.
    """
    return Decision(
        id=row.id,
        meeting_id=row.meeting_id,
        description=row.description,
        decided_by_id=row.decided_by_id,
        participants_present=[UUID(p) for p in row.participants_present],
        created_at=row.created_at,
    )


class StructuredMemory:
    """PostgreSQL-backed structured memory for indexed queries.

    Provides direct queries against the tasks and decisions tables
    with filtering by assignee, meeting, status, and dependency
    relationships. Returns domain model instances.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize structured memory with a SQLAlchemy session factory.

        Args:
            session_factory: An async session factory for database access.
        """
        self._session_factory = session_factory

    async def get_open_tasks(
        self,
        assignee_id: UUID | None = None,
    ) -> list[Task]:
        """Retrieve all open (non-done) tasks, optionally filtered by assignee.

        Args:
            assignee_id: If provided, filter tasks to this assignee only.

        Returns:
            List of Task domain models with status other than DONE,
            ordered by creation date descending.
        """
        async with self._session_factory() as session:
            stmt = (
                select(TaskRow)
                .where(TaskRow.status != TaskStatus.DONE.value)
                .order_by(TaskRow.created_at.desc())
            )
            if assignee_id is not None:
                stmt = stmt.where(TaskRow.assignee_id == assignee_id)

            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_task_row_to_model(row) for row in rows]

    async def get_decisions(self, meeting_id: UUID) -> list[Decision]:
        """Retrieve all decisions recorded in a specific meeting.

        Args:
            meeting_id: UUID of the meeting to query.

        Returns:
            List of Decision domain models ordered by creation date.
        """
        async with self._session_factory() as session:
            stmt = (
                select(DecisionRow)
                .where(DecisionRow.meeting_id == meeting_id)
                .order_by(DecisionRow.created_at.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_decision_row_to_model(row) for row in rows]

    async def get_task_dependencies(self, task_id: UUID) -> list[Task]:
        """Retrieve all tasks that the given task depends on.

        Looks up the dependency UUIDs for the specified task and
        fetches each dependency task record.

        Args:
            task_id: UUID of the task whose dependencies to retrieve.

        Returns:
            List of Task domain models that are dependencies of the
            given task. Returns empty list if the task has no
            dependencies or if the task is not found.
        """
        async with self._session_factory() as session:
            # First, get the task to find its dependencies
            task_stmt = select(TaskRow).where(TaskRow.id == task_id)
            task_result = await session.execute(task_stmt)
            task_row = task_result.scalar_one_or_none()

            if task_row is None:
                logger.warning(
                    "Task %s not found for dependency lookup.",
                    task_id,
                )
                return []

            if not task_row.dependencies:
                return []

            # Parse dependency UUIDs
            dep_uuids: list[UUID] = []
            for dep_str in task_row.dependencies:
                try:
                    dep_uuids.append(UUID(dep_str))
                except ValueError:
                    logger.warning(
                        "Invalid dependency UUID: %s",
                        dep_str,
                    )

            if not dep_uuids:
                return []

            # Fetch all dependency tasks
            deps_stmt = select(TaskRow).where(TaskRow.id.in_(dep_uuids))
            deps_result = await session.execute(deps_stmt)
            dep_rows = deps_result.scalars().all()
            return [_task_row_to_model(row) for row in dep_rows]
