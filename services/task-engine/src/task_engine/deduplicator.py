"""Task deduplication against existing tasks in the database."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
    )

    from convene_core.models.task import Task

logger = logging.getLogger(__name__)

# Similarity threshold above which two task descriptions are
# considered duplicates.  Tuned conservatively to avoid false
# positives.
_SIMILARITY_THRESHOLD = 0.85


class TaskDeduplicator:
    """Filters out duplicate tasks by comparing descriptions.

    Compares newly extracted tasks against existing tasks for the
    same meeting using sequence-based string similarity.

    Attributes:
        _session_factory: Async session factory for database access.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialise the deduplicator.

        Args:
            session_factory: SQLAlchemy async session factory.
        """
        self._session_factory = session_factory

    async def deduplicate(
        self,
        new_tasks: list[Task],
        meeting_id: UUID,
    ) -> list[Task]:
        """Remove tasks that are duplicates of existing records.

        Fetches all existing tasks for the given meeting, then
        compares each new task's description against them using
        SequenceMatcher.  Only genuinely new tasks are returned.

        Args:
            new_tasks: Candidate tasks freshly extracted by the LLM.
            meeting_id: The meeting these tasks belong to.

        Returns:
            A filtered list containing only non-duplicate tasks.
        """
        if not new_tasks:
            return []

        existing_descriptions = await self._fetch_existing_descriptions(meeting_id)

        if not existing_descriptions:
            logger.debug(
                "No existing tasks for meeting %s; all candidates are new",
                meeting_id,
            )
            return list(new_tasks)

        unique_tasks: list[Task] = []
        for task in new_tasks:
            if self._is_duplicate(task.description, existing_descriptions):
                logger.debug(
                    "Duplicate task skipped: %s",
                    task.description[:60],
                )
            else:
                unique_tasks.append(task)

        logger.info(
            "Deduplication: %d candidates -> %d unique tasks",
            len(new_tasks),
            len(unique_tasks),
        )
        return unique_tasks

    async def _fetch_existing_descriptions(
        self,
        meeting_id: UUID,
    ) -> list[str]:
        """Fetch descriptions of all existing tasks for a meeting.

        Args:
            meeting_id: The meeting whose tasks to retrieve.

        Returns:
            List of task description strings.
        """
        async with self._session_factory() as session:
            # Placeholder query — will use the ORM Task model once
            # the database layer is fully wired up.
            from sqlalchemy import text

            result = await session.execute(
                text("SELECT description FROM tasks WHERE meeting_id = :mid"),
                {"mid": str(meeting_id)},
            )
            rows = result.fetchall()
            return [str(row[0]) for row in rows]

    @staticmethod
    def _is_duplicate(
        description: str,
        existing: list[str],
    ) -> bool:
        """Check whether a description is similar to any existing one.

        Uses SequenceMatcher ratio for fuzzy string comparison.

        Args:
            description: The candidate task description.
            existing: List of existing task descriptions to compare.

        Returns:
            True if the description is a duplicate, False otherwise.
        """
        normalised = description.strip().lower()
        for existing_desc in existing:
            ratio = SequenceMatcher(
                None,
                normalised,
                existing_desc.strip().lower(),
            ).ratio()
            if ratio >= _SIMILARITY_THRESHOLD:
                return True
        return False
