"""LLM-powered task extraction from transcript segments."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kutana_core.database.models import TaskORM
from kutana_core.events.definitions import TaskCreated

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

    from kutana_core.interfaces.llm import LLMProvider
    from kutana_core.models.task import Task
    from kutana_core.models.transcript import TranscriptSegment
    from task_engine.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class TaskExtractor:
    """Extracts actionable tasks from meeting transcript segments.

    Uses an LLM provider to analyse transcript text and produce
    structured Task objects.  Extracted tasks are persisted to the
    database via the provided session factory.  After each successful
    persist, a ``task.created`` event is published to Redis if an
    :class:`EventPublisher` is configured.

    Attributes:
        _llm: The LLM provider used for extraction.
        _session_factory: Async session factory for database access.
        _event_publisher: Optional publisher for domain events.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        session_factory: async_sessionmaker[AsyncSession],
        event_publisher: EventPublisher | None = None,
    ) -> None:
        """Initialise the task extractor.

        Args:
            llm_provider: An LLM provider implementing the LLMProvider ABC.
            session_factory: SQLAlchemy async session factory for persistence.
            event_publisher: Optional Redis event publisher.  When provided,
                a ``task.created`` event is emitted for every persisted task.
        """
        self._llm = llm_provider
        self._session_factory = session_factory
        self._event_publisher = event_publisher

    async def extract_from_segments(
        self,
        segments: list[TranscriptSegment],
        context: str,
    ) -> list[Task]:
        """Extract tasks from a list of transcript segments.

        Sends the segments and contextual information to the LLM
        provider for structured extraction, then persists each
        resulting task to the database and emits a ``task.created``
        event for each new task.

        Args:
            segments: Transcript segments to analyse for tasks.
            context: Additional context such as participant names,
                open tasks, or meeting history.

        Returns:
            List of newly extracted Task objects.
        """
        if not segments:
            logger.debug("No segments provided; skipping extraction")
            return []

        logger.info("Extracting tasks from %d segments", len(segments))

        tasks = await self._llm.extract_tasks(segments, context)

        if not tasks:
            logger.info("No tasks extracted from segments")
            return []

        await self._persist_tasks(tasks)
        await self._emit_task_created_events(tasks)

        logger.info("Extracted and persisted %d tasks", len(tasks))
        return tasks

    async def _persist_tasks(self, tasks: list[Task]) -> None:
        """Store extracted tasks in the database using ORM models.

        Opens a new async session, maps each domain ``Task`` to a
        ``TaskORM`` row, and commits the transaction.  If anything
        fails the session is rolled back so no partial data is written.

        Args:
            tasks: List of Task domain models to persist.
        """
        async with self._session_factory() as session:
            try:
                for task in tasks:
                    orm_task = TaskORM(
                        id=task.id,
                        meeting_id=task.meeting_id,
                        description=task.description,
                        assignee_id=task.assignee_id,
                        due_date=task.due_date,
                        priority=str(task.priority),
                        status=str(task.status),
                        # Convert UUID list to string list for JSONB storage
                        dependencies=[str(dep) for dep in task.dependencies],
                        source_utterance=task.source_utterance,
                        created_at=task.created_at,
                        updated_at=task.updated_at,
                    )
                    session.add(orm_task)
                    logger.debug(
                        "Queued task for insert: id=%s, desc=%s",
                        task.id,
                        task.description[:60],
                    )
                await session.commit()
                logger.info("Persisted %d tasks to database", len(tasks))
            except Exception:
                await session.rollback()
                logger.exception("Failed to persist extracted tasks")
                raise

    async def _emit_task_created_events(self, tasks: list[Task]) -> None:
        """Emit a ``task.created`` event for each persisted task.

        If no :class:`EventPublisher` is configured, this method is a
        no-op.  Publish errors are logged and swallowed so that a Redis
        outage does not prevent successful extraction.

        Args:
            tasks: Newly persisted Task domain models.
        """
        if self._event_publisher is None:
            return

        for task in tasks:
            try:
                event = TaskCreated(task=task)
                entry_id = await self._event_publisher.publish(event)
                logger.debug(
                    "Emitted task.created: task_id=%s entry=%s",
                    task.id,
                    entry_id,
                )
            except Exception:
                logger.exception(
                    "Failed to publish task.created for task_id=%s — continuing",
                    task.id,
                )
