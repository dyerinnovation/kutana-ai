"""Anthropic Claude LLM provider for task extraction and summarization."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import anthropic

from kutana_core.interfaces.llm import LLMProvider
from kutana_core.models.task import Task, TaskPriority

if TYPE_CHECKING:
    from kutana_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_EXTRACT_TEMPERATURE = 0.0
_EXTRACT_MAX_TOKENS = 4096
_SUMMARIZE_MAX_TOKENS = 2048
_REPORT_MAX_TOKENS = 4096

# Tool definition for structured task extraction via Claude tool_use
_TASK_EXTRACTION_TOOL: dict[str, Any] = {
    "name": "extract_tasks",
    "description": (
        "Extract actionable tasks from meeting transcript segments. "
        "Each task should have a clear description, optional assignee "
        "name, optional due date, and priority level."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "List of extracted tasks.",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": ("Clear, actionable task description."),
                        },
                        "assignee_name": {
                            "type": "string",
                            "description": ("Name of person assigned, if mentioned."),
                        },
                        "due_date": {
                            "type": "string",
                            "description": (
                                "Due date in ISO 8601 format, if mentioned. Example: 2025-03-15"
                            ),
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Task priority level.",
                        },
                        "source_utterance": {
                            "type": "string",
                            "description": (
                                "The original transcript text that indicates this task."
                            ),
                        },
                    },
                    "required": [
                        "description",
                        "priority",
                        "source_utterance",
                    ],
                },
            },
        },
        "required": ["tasks"],
    },
}


def _format_segments_for_prompt(
    segments: list[TranscriptSegment],
) -> str:
    """Format transcript segments into a readable string for the LLM.

    Args:
        segments: List of transcript segments to format.

    Returns:
        A formatted string with speaker labels and timestamps.
    """
    lines: list[str] = []
    for seg in segments:
        speaker = seg.speaker_id or "Unknown"
        timestamp = f"[{seg.start_time:.1f}s - {seg.end_time:.1f}s]"
        lines.append(f"{timestamp} {speaker}: {seg.text}")
    return "\n".join(lines)


class AnthropicLLM(LLMProvider):
    """Anthropic Claude LLM provider.

    Uses the Anthropic Python SDK with AsyncAnthropic client for
    task extraction, summarization, and report generation.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        """Initialize the Anthropic LLM provider.

        Args:
            api_key: Anthropic API key for authentication.
            model: Claude model ID to use for inference.
        """
        self._api_key = api_key
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def extract_tasks(
        self,
        segments: list[TranscriptSegment],
        context: str,
    ) -> list[Task]:
        """Extract actionable tasks from transcript segments using Claude.

        Sends the transcript segments and additional context to Claude
        with a tool_use definition for structured task extraction. Parses
        the tool_use response into a list of Task models.

        Args:
            segments: List of transcript segments to analyze.
            context: Additional context such as participant names,
                open tasks, and meeting history.

        Returns:
            List of extracted Task objects.
        """
        if not segments:
            return []

        formatted_transcript = _format_segments_for_prompt(segments)
        meeting_id = segments[0].meeting_id

        system_prompt = (
            "You are an AI meeting assistant that extracts actionable "
            "tasks from meeting transcripts. Identify commitments, "
            "action items, and follow-ups mentioned by participants. "
            "Only extract clear, actionable tasks -- not general "
            "discussion points.\n\n"
            f"Additional context:\n{context}"
        )

        user_message = (
            "Analyze the following meeting transcript and extract all "
            "actionable tasks. Use the extract_tasks tool to return "
            "structured results.\n\n"
            f"Transcript:\n{formatted_transcript}"
        )

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=_EXTRACT_MAX_TOKENS,
            temperature=_EXTRACT_TEMPERATURE,
            system=system_prompt,
            tools=[_TASK_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_tasks"},
            messages=[{"role": "user", "content": user_message}],
        )

        tasks: list[Task] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name != "extract_tasks":
                continue

            tool_input: dict[str, Any] = block.input  # type: ignore[assignment]  # Anthropic SDK tool_input typed as object
            raw_tasks: list[dict[str, Any]] = tool_input.get("tasks", [])

            for raw in raw_tasks:
                priority_str = raw.get("priority", "medium")
                try:
                    priority = TaskPriority(priority_str)
                except ValueError:
                    priority = TaskPriority.MEDIUM

                due_date_str = raw.get("due_date")
                due_date = None
                if due_date_str:
                    from datetime import date

                    try:
                        due_date = date.fromisoformat(due_date_str)
                    except ValueError:
                        logger.warning("Invalid due_date: %s", due_date_str)

                task = Task(
                    id=uuid4(),
                    meeting_id=meeting_id,
                    description=raw.get("description", ""),
                    priority=priority,
                    due_date=due_date,
                    source_utterance=raw.get("source_utterance"),
                )
                tasks.append(task)

        logger.info(
            "Extracted %d tasks from %d segments.",
            len(tasks),
            len(segments),
        )
        return tasks

    async def summarize(self, segments: list[TranscriptSegment]) -> str:
        """Generate a concise summary of transcript segments.

        Args:
            segments: List of transcript segments to summarize.

        Returns:
            A human-readable summary string.
        """
        if not segments:
            return ""

        formatted_transcript = _format_segments_for_prompt(segments)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=_SUMMARIZE_MAX_TOKENS,
            temperature=0.3,
            system=(
                "You are an AI meeting assistant. Produce a concise, "
                "well-structured summary of the meeting transcript. "
                "Focus on key discussion points, decisions made, and "
                "action items mentioned."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Summarize the following meeting transcript:\n\n{formatted_transcript}"
                    ),
                }
            ],
        )

        # Extract text from the response content blocks
        parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)

        summary = "\n".join(parts).strip()
        logger.info(
            "Generated summary of %d characters from %d segments.",
            len(summary),
            len(segments),
        )
        return summary

    async def generate_report(self, tasks: list[Task]) -> str:
        """Generate a formatted report from a list of tasks.

        Args:
            tasks: List of tasks to include in the report.

        Returns:
            A formatted report string suitable for sharing.
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

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=_REPORT_MAX_TOKENS,
            temperature=0.2,
            system=(
                "You are an AI meeting assistant. Generate a clear, "
                "professional report from the provided task list. "
                "Group tasks by status, highlight blockers, and "
                "include a brief executive summary at the top."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Generate a formatted report from these meeting tasks:\n\n{tasks_text}"
                    ),
                }
            ],
        )

        parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)

        report = "\n".join(parts).strip()
        logger.info(
            "Generated report of %d characters for %d tasks.",
            len(report),
            len(tasks),
        )
        return report

    async def close(self) -> None:
        """Close the underlying Anthropic client."""
        await self._client.close()
