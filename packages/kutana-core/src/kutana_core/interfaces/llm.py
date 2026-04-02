"""LLM provider interface for task extraction and summarization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kutana_core.models.task import Task
    from kutana_core.models.transcript import TranscriptSegment


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Implementations handle task extraction, summarization, and
    report generation from meeting transcript segments.
    """

    @abstractmethod
    async def extract_tasks(self, segments: list[TranscriptSegment], context: str) -> list[Task]:
        """Extract actionable tasks from transcript segments.

        Args:
            segments: List of transcript segments to analyze.
            context: Additional context (e.g., memory, participant info).

        Returns:
            List of extracted Task objects.
        """
        ...

    @abstractmethod
    async def summarize(self, segments: list[TranscriptSegment]) -> str:
        """Generate a concise summary of the transcript segments.

        Args:
            segments: List of transcript segments to summarize.

        Returns:
            A human-readable summary string.
        """
        ...

    @abstractmethod
    async def generate_report(self, tasks: list[Task]) -> str:
        """Generate a formatted report from a list of tasks.

        Args:
            tasks: List of tasks to include in the report.

        Returns:
            A formatted report string.
        """
        ...
