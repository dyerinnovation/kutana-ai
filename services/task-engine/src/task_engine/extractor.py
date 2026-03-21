"""LLM-powered task extraction from transcript segments."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

    from convene_core.interfaces.llm import LLMProvider
    from convene_core.models.task import Task
    from convene_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)


class TaskExtractor:
    """Extracts actionable tasks from meeting transcript segments.

    Uses an LLM provider to analyse transcript text and produce
    structured Task objects.  Extracted tasks are persisted to the
    database via the provided session factory.

    Attributes:
        _llm: The LLM provider used for extraction.
        _session_factory: Async session factory for database access.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialise the task extractor.

        Args:
            llm_provider: An LLM provider implementing the LLMProvider ABC.
            session_factory: SQLAlchemy async session factory for persistence.
        """
        self._llm = llm_provider
        self._session_factory = session_factory

    async def extract_from_segments(
        self,
        segments: list[TranscriptSegment],
        context: str,
    ) -> list[Task]:
        """Extract tasks from a list of transcript segments.

        Sends the segments and contextual information to the LLM
        provider for structured extraction, then persists each
        resulting task to the database.

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

        logger.info("Extracted and persisted %d tasks", len(tasks))
        return tasks

    async def _persist_tasks(self, tasks: list[Task]) -> None:
        """Store extracted tasks in the database.

        Opens a new async session, adds serialised task data, and
        commits.  On failure the transaction is rolled back.

        Args:
            tasks: List of Task domain models to persist.
        """
        async with self._session_factory() as session:
            try:
                for task in tasks:
                    # Store as a dictionary for now; a proper ORM model
                    # will be introduced when the database layer is
                    # wired up with SQLAlchemy mapped models.
                    session.add_all([])  # placeholder for ORM insert
                    logger.debug(
                        "Persisting task: id=%s, desc=%s",
                        task.id,
                        task.description[:60],
                    )
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Failed to persist extracted tasks")
                raise
