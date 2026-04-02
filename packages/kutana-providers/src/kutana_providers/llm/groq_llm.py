"""Groq LLM provider for task extraction and summarization."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from kutana_core.interfaces.llm import LLMProvider
from kutana_core.models.task import Task, TaskPriority

if TYPE_CHECKING:
    from kutana_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = (
    "You are an AI meeting assistant that extracts actionable "
    "tasks from meeting transcripts. Identify commitments, "
    "action items, and follow-ups mentioned by participants. "
    "Only extract clear, actionable tasks -- not general "
    "discussion points.\n\n"
    "Return a JSON object with a single key 'tasks' containing "
    "an array of task objects. Each task object must have:\n"
    '  - "description": clear actionable description\n'
    '  - "priority": one of "low", "medium", "high", "critical"\n'
    '  - "assignee_name": name of person assigned (or null)\n'
    '  - "due_date": ISO 8601 date string (or null)\n'
    '  - "source_utterance": original transcript text that '
    "indicates this task"
)

_SUMMARIZE_SYSTEM = (
    "You are an AI meeting assistant. Produce a concise, "
    "well-structured summary of the meeting transcript. Focus "
    "on key discussion points, decisions made, and action items "
    "mentioned."
)

_REPORT_SYSTEM = (
    "You are an AI meeting assistant. Generate a clear, "
    "professional report from the provided task list. Group "
    "tasks by status, highlight blockers, and include a brief "
    "executive summary at the top."
)


class GroqLLM(LLMProvider):
    """Groq LLM provider. Free tier, no credit card required.

    Uses the Groq Python SDK with ``AsyncGroq`` for fast
    inference on open-source models hosted on Groq's LPU
    infrastructure.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
    ) -> None:
        """Initialize the Groq LLM provider.

        Args:
            api_key: Groq API key for authentication.
            model: Groq model ID to use for inference.
        """
        from groq import AsyncGroq

        self._model = model
        self._client = AsyncGroq(api_key=api_key)

    async def extract_tasks(
        self,
        segments: list[TranscriptSegment],
        context: str,
    ) -> list[Task]:
        """Extract actionable tasks from transcript segments.

        Sends the formatted transcript to Groq with a structured
        JSON prompt and parses the response into Task objects.

        Args:
            segments: List of transcript segments to analyze.
            context: Additional context (e.g., participant info).

        Returns:
            List of extracted Task objects.
        """
        if not segments:
            return []

        transcript = self._format_segments(segments)
        meeting_id = segments[0].meeting_id

        user_content = (
            f"Additional context:\n{context}\n\n"
            "Analyze the following meeting transcript and "
            "extract all actionable tasks.\n\n"
            f"Transcript:\n{transcript}"
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        raw_content = response.choices[0].message.content or ""

        try:
            data: dict[str, Any] = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse Groq JSON response for task extraction.")
            return []

        tasks: list[Task] = []
        for raw_task in data.get("tasks", []):
            priority_str = raw_task.get("priority", "medium")
            try:
                priority = TaskPriority(priority_str)
            except ValueError:
                priority = TaskPriority.MEDIUM

            due_date_val: date | None = None
            due_date_str = raw_task.get("due_date")
            if due_date_str:
                try:
                    due_date_val = date.fromisoformat(
                        due_date_str,
                    )
                except ValueError:
                    logger.warning(
                        "Invalid due_date: %s",
                        due_date_str,
                    )

            task = Task(
                id=uuid4(),
                meeting_id=meeting_id,
                description=raw_task.get("description", ""),
                priority=priority,
                due_date=due_date_val,
                source_utterance=raw_task.get("source_utterance"),
            )
            tasks.append(task)

        logger.info(
            "Extracted %d tasks from %d segments via Groq.",
            len(tasks),
            len(segments),
        )
        return tasks

    async def summarize(
        self,
        segments: list[TranscriptSegment],
    ) -> str:
        """Generate a concise summary of transcript segments.

        Args:
            segments: List of transcript segments to summarize.

        Returns:
            A human-readable summary string.
        """
        if not segments:
            return ""

        transcript = self._format_segments(segments)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": _SUMMARIZE_SYSTEM,
                },
                {
                    "role": "user",
                    "content": (f"Summarize the following meeting transcript:\n\n{transcript}"),
                },
            ],
            temperature=0.3,
        )

        summary = response.choices[0].message.content or ""
        logger.info(
            "Generated summary of %d chars from %d segments.",
            len(summary),
            len(segments),
        )
        return summary.strip()

    async def generate_report(self, tasks: list[Task]) -> str:
        """Generate a formatted report from a list of tasks.

        Args:
            tasks: List of tasks to include in the report.

        Returns:
            A formatted report string.
        """
        if not tasks:
            return "No tasks to report."

        task_lines: list[str] = []
        for task in tasks:
            assignee = str(task.assignee_id) if task.assignee_id else "Unassigned"
            due = str(task.due_date) if task.due_date else "No due date"
            task_lines.append(
                f"- [{task.status.value}] {task.description} "
                f"(Assignee: {assignee}, Due: {due}, "
                f"Priority: {task.priority.value})"
            )

        tasks_text = "\n".join(task_lines)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": _REPORT_SYSTEM,
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a formatted report from these meeting tasks:\n\n{tasks_text}"
                    ),
                },
            ],
            temperature=0.2,
        )

        report = response.choices[0].message.content or ""
        logger.info(
            "Generated report of %d chars for %d tasks.",
            len(report),
            len(tasks),
        )
        return report.strip()

    def _format_segments(
        self,
        segments: list[TranscriptSegment],
    ) -> str:
        """Format transcript segments into readable text.

        Args:
            segments: List of transcript segments.

        Returns:
            Formatted string with timestamps and speakers.
        """
        lines: list[str] = []
        for seg in segments:
            speaker = seg.speaker_id or "Unknown"
            timestamp = f"[{seg.start_time:.1f}-{seg.end_time:.1f}]"
            lines.append(f"{timestamp} {speaker}: {seg.text}")
        return "\n".join(lines)

    async def close(self) -> None:
        """Close the underlying Groq client."""
        await self._client.close()
