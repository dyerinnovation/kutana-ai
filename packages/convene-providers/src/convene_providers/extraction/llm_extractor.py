"""Anthropic-backed LLM extractor for the Meeting Insight Stream pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any

import anthropic

from convene_core.extraction.abc import Extractor
from convene_core.extraction.types import (
    AnyExtractedEntity,
    BlockerEntity,
    DecisionEntity,
    EntityMentionEntity,
    ExtractionResult,
    FollowUpEntity,
    KeyPointEntity,
    QuestionEntity,
    TaskEntity,
    TranscriptBatch,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_EXTRACT_MAX_TOKENS = 8192

_ALL_ENTITY_TYPES = [
    "task",
    "decision",
    "question",
    "entity_mention",
    "key_point",
    "blocker",
    "follow_up",
]

# ---------------------------------------------------------------------------
# Anthropic tool schema for structured entity extraction
# ---------------------------------------------------------------------------

_EXTRACTION_TOOL: dict[str, Any] = {
    "name": "extract_meeting_entities",
    "description": (
        "Extract structured entities from a meeting transcript batch. "
        "Identify all tasks, decisions, questions, entity mentions, key points, "
        "blockers, and follow-ups. Only extract entities clearly present in the "
        "transcript. Use lowercase for all enum values."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "Action items and commitments identified in the transcript.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Clear, actionable task description.",
                        },
                        "assignee": {
                            "type": "string",
                            "description": "Name of the person assigned, if mentioned.",
                        },
                        "deadline": {
                            "type": "string",
                            "description": "Deadline or due date as mentioned in transcript.",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Task priority level.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["identified", "accepted", "completed"],
                            "description": "Task lifecycle status.",
                        },
                        "source_speaker": {
                            "type": "string",
                            "description": "Speaker who stated or accepted the task.",
                        },
                        "source_segment_id": {
                            "type": "string",
                            "description": "Segment ID where the task was mentioned.",
                        },
                    },
                    "required": ["title"],
                },
            },
            "decisions": {
                "type": "array",
                "description": "Decisions made during the meeting.",
                "items": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Concise description of what was decided.",
                        },
                        "participants": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of participants involved.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Reasoning behind the decision, if stated.",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence that this is a genuine decision.",
                        },
                        "source_segment_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of supporting segments.",
                        },
                    },
                    "required": ["summary"],
                },
            },
            "questions": {
                "type": "array",
                "description": "Questions raised during the meeting.",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The question text as asked.",
                        },
                        "asker": {
                            "type": "string",
                            "description": "Name of the person who asked.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["open", "answered"],
                            "description": "Whether the question was answered.",
                        },
                        "answer": {
                            "type": "string",
                            "description": "The answer given, if resolved.",
                        },
                        "source_segment_id": {"type": "string"},
                    },
                    "required": ["text"],
                },
            },
            "entity_mentions": {
                "type": "array",
                "description": "Named entities (people, systems, concepts, orgs) mentioned.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Canonical name of the mentioned entity.",
                        },
                        "kind": {
                            "type": "string",
                            "enum": ["person", "system", "concept", "org"],
                            "description": "Category of the entity.",
                        },
                        "context": {
                            "type": "string",
                            "description": "Brief context around the first mention.",
                        },
                        "first_mention_segment_id": {"type": "string"},
                    },
                    "required": ["name", "kind"],
                },
            },
            "key_points": {
                "type": "array",
                "description": "Significant points or insights from the discussion.",
                "items": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "The key point as a concise statement.",
                        },
                        "speaker": {"type": "string"},
                        "topic": {
                            "type": "string",
                            "description": "Topic or theme this point belongs to.",
                        },
                        "importance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "source_segment_id": {"type": "string"},
                    },
                    "required": ["summary"],
                },
            },
            "blockers": {
                "type": "array",
                "description": "Impediments or blockers raised during the meeting.",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Clear description of the blocker.",
                        },
                        "owner": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                        },
                        "related_tasks": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "source_segment_id": {"type": "string"},
                    },
                    "required": ["description"],
                },
            },
            "follow_ups": {
                "type": "array",
                "description": "Follow-up items to be actioned after the meeting.",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What needs to be followed up on.",
                        },
                        "owner": {"type": "string"},
                        "due_context": {
                            "type": "string",
                            "description": "Timing or deadline context from transcript.",
                        },
                        "source_segment_id": {"type": "string"},
                    },
                    "required": ["description"],
                },
            },
        },
        "required": [
            "tasks",
            "decisions",
            "questions",
            "entity_mentions",
            "key_points",
            "blockers",
            "follow_ups",
        ],
    },
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_batch(batch: TranscriptBatch) -> str:
    """Format a ``TranscriptBatch`` into a readable string for the LLM prompt.

    Args:
        batch: The batch to format.

    Returns:
        Multi-line string with speaker labels and segment IDs.
    """
    lines: list[str] = []

    if batch.context_segments:
        lines.append("=== Previous context (for continuity) ===")
        # Include up to the last 5 context segments to stay within token limits
        for seg in batch.context_segments[-5:]:
            speaker = seg.speaker or "Unknown"
            lines.append(f"[seg:{seg.segment_id}] {speaker}: {seg.text}")
        lines.append("=== Current batch ===")

    for seg in batch.segments:
        speaker = seg.speaker or "Unknown"
        lines.append(f"[seg:{seg.segment_id}] {speaker}: {seg.text}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLMExtractor
# ---------------------------------------------------------------------------


class LLMExtractor(Extractor):
    """Entity extractor powered by Anthropic Claude.

    Uses Claude's tool-use feature with a structured schema to extract all
    seven entity types from a ``TranscriptBatch`` in a single API call.

    Args:
        api_key: Anthropic API key for authentication.
        model: Claude model ID to use.  Defaults to claude-sonnet-4-20250514.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        """Initialize the LLM extractor."""
        self._api_key = api_key
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        """Unique name for this extractor."""
        return "llm-extractor"

    @property
    def entity_types(self) -> list[str]:
        """All seven entity types produced by this extractor."""
        return list(_ALL_ENTITY_TYPES)

    async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
        """Extract all entity types from a transcript batch via Claude.

        Constructs a prompt from the batch segments and calls Claude with
        the ``extract_meeting_entities`` tool to get structured results.
        Parses the tool response into typed ``ExtractedEntity`` objects.

        Args:
            batch: The windowed transcript batch to process.

        Returns:
            An ``ExtractionResult`` with all extracted entities.
        """
        start = time.monotonic()

        if not batch.segments:
            return ExtractionResult(
                batch_id=batch.batch_id,
                entities=[],
                processing_time_ms=0.0,
            )

        transcript_text = _format_batch(batch)

        system_prompt = (
            "You are an AI meeting analyst. Your task is to extract structured "
            "entities from meeting transcript batches. Be precise — only extract "
            "entities that are clearly present in the transcript. Do not infer "
            "entities that are not explicitly mentioned. Use lowercase for all "
            "enum values (priority, status, severity, importance, kind)."
        )

        user_message = (
            f"Meeting ID: {batch.meeting_id}\n"
            f"Batch ID: {batch.batch_id}\n\n"
            f"Transcript:\n{transcript_text}\n\n"
            "Use the extract_meeting_entities tool to extract all entities."
        )

        response = await self._client.messages.create(  # type: ignore[call-overload]
            model=self._model,
            max_tokens=_EXTRACT_MAX_TOKENS,
            temperature=0.0,
            system=system_prompt,
            tools=[_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_meeting_entities"},
            messages=[{"role": "user", "content": user_message}],
        )

        entities: list[AnyExtractedEntity] = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_meeting_entities":
                tool_input: dict[str, Any] = block.input
                entities = self._parse_entities(tool_input, batch)
                break

        processing_ms = (time.monotonic() - start) * 1000.0
        logger.info(
            "LLMExtractor extracted %d entities from batch %s in %.1f ms",
            len(entities),
            batch.batch_id,
            processing_ms,
        )

        return ExtractionResult(
            batch_id=batch.batch_id,
            entities=entities,
            processing_time_ms=processing_ms,
        )

    def _parse_entities(
        self,
        tool_input: dict[str, Any],
        batch: TranscriptBatch,
    ) -> list[AnyExtractedEntity]:
        """Parse the Anthropic tool-use response into typed entity objects.

        Uses Pydantic ``model_validate`` to build each entity, injecting the
        ``meeting_id`` and ``batch_id`` from the batch into each raw dict.

        Args:
            tool_input: The ``input`` field from the tool-use response block.
            batch: The batch being processed (provides meeting/batch IDs).

        Returns:
            List of validated entity objects.
        """
        entities: list[AnyExtractedEntity] = []
        meeting_id = batch.meeting_id
        batch_id = batch.batch_id

        def _base(confidence: float = 0.85) -> dict[str, Any]:
            return {
                "meeting_id": meeting_id,
                "batch_id": batch_id,
                "confidence": confidence,
            }

        for raw in tool_input.get("tasks", []):
            try:
                entity: AnyExtractedEntity = TaskEntity.model_validate(
                    {**_base(), **raw}
                )
                entities.append(entity)
            except Exception:
                logger.warning("LLMExtractor: skipping invalid task: %s", raw)

        for raw in tool_input.get("decisions", []):
            try:
                conf = float(raw.get("confidence", 0.8))
                entity = DecisionEntity.model_validate({**_base(conf), **raw})
                entities.append(entity)
            except Exception:
                logger.warning("LLMExtractor: skipping invalid decision: %s", raw)

        for raw in tool_input.get("questions", []):
            try:
                entity = QuestionEntity.model_validate({**_base(), **raw})
                entities.append(entity)
            except Exception:
                logger.warning("LLMExtractor: skipping invalid question: %s", raw)

        for raw in tool_input.get("entity_mentions", []):
            try:
                entity = EntityMentionEntity.model_validate({**_base(0.9), **raw})
                entities.append(entity)
            except Exception:
                logger.warning(
                    "LLMExtractor: skipping invalid entity_mention: %s", raw
                )

        for raw in tool_input.get("key_points", []):
            try:
                entity = KeyPointEntity.model_validate({**_base(), **raw})
                entities.append(entity)
            except Exception:
                logger.warning("LLMExtractor: skipping invalid key_point: %s", raw)

        for raw in tool_input.get("blockers", []):
            try:
                entity = BlockerEntity.model_validate({**_base(0.9), **raw})
                entities.append(entity)
            except Exception:
                logger.warning("LLMExtractor: skipping invalid blocker: %s", raw)

        for raw in tool_input.get("follow_ups", []):
            try:
                entity = FollowUpEntity.model_validate({**_base(), **raw})
                entities.append(entity)
            except Exception:
                logger.warning("LLMExtractor: skipping invalid follow_up: %s", raw)

        return entities

    async def close(self) -> None:
        """Close the underlying Anthropic client."""
        await self._client.close()
