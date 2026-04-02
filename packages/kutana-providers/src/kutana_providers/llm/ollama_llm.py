"""Local LLM provider using Ollama REST API."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx

from kutana_core.interfaces.llm import LLMProvider
from kutana_core.models.task import Task, TaskPriority

if TYPE_CHECKING:
    from kutana_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = (
    "You are an AI meeting assistant. Extract actionable tasks "
    "from the following transcript. Return a JSON object with a "
    "single key 'tasks' containing an array of task objects. "
    "Each task object must have:\n"
    '  - "description": clear actionable description\n'
    '  - "priority": one of "low", "medium", "high", "critical"\n'
    '  - "assignee_name": name of person assigned (or null)\n'
    '  - "due_date": ISO 8601 date string (or null)\n'
    '  - "source_utterance": original text that indicates this task\n'
    "\nOnly extract clear, actionable tasks -- not general "
    "discussion points.\n\n"
    "Additional context:\n{context}\n\n"
    "Transcript:\n{transcript}"
)

_SUMMARIZE_PROMPT = (
    "You are an AI meeting assistant. Produce a concise, "
    "well-structured summary of the following meeting transcript. "
    "Focus on key discussion points, decisions made, and action "
    "items mentioned.\n\n"
    "Transcript:\n{transcript}"
)

_REPORT_PROMPT = (
    "You are an AI meeting assistant. Generate a clear, "
    "professional report from the provided task list. Group "
    "tasks by status, highlight blockers, and include a brief "
    "executive summary at the top.\n\n"
    "Tasks:\n{tasks}"
)


class OllamaLLM(LLMProvider):
    """Local LLM provider using Ollama. No API key required.

    Communicates with a locally running Ollama instance via its
    REST API for task extraction, summarization, and report
    generation.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
    ) -> None:
        """Initialize the Ollama LLM provider.

        Args:
            base_url: URL of the local Ollama server.
            model: Ollama model name to use for inference.
        """
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

    async def extract_tasks(
        self,
        segments: list[TranscriptSegment],
        context: str,
    ) -> list[Task]:
        """Extract actionable tasks from transcript segments.

        Sends the formatted transcript to Ollama with a structured
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

        prompt = _EXTRACT_PROMPT.format(
            context=context,
            transcript=transcript,
        )

        raw = await self._generate(prompt, json_format=True)

        try:
            data: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse Ollama JSON response for task extraction.")
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
                    due_date_val = date.fromisoformat(due_date_str)
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
            "Extracted %d tasks from %d segments via Ollama.",
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
        prompt = _SUMMARIZE_PROMPT.format(transcript=transcript)
        summary = await self._generate(prompt)

        logger.info(
            "Generated summary of %d chars from %d segments.",
            len(summary),
            len(segments),
        )
        return summary

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
        prompt = _REPORT_PROMPT.format(tasks=tasks_text)
        report = await self._generate(prompt)

        logger.info(
            "Generated report of %d chars for %d tasks.",
            len(report),
            len(tasks),
        )
        return report

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

    async def _generate(
        self,
        prompt: str,
        *,
        json_format: bool = False,
    ) -> str:
        """Send a generation request to the Ollama API.

        Args:
            prompt: The prompt text to send.
            json_format: If True, request JSON-formatted output.

        Returns:
            The generated text from Ollama.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if json_format:
            payload["format"] = "json"

        url = f"{self._base_url}/api/generate"
        response = await self._client.post(url, json=payload)
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        return data.get("response", "")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
