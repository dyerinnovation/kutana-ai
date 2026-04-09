"""Helper utilities for building custom Kutana AI extractors.

This module provides:

- :func:`extractor` — a class decorator for quick extractor definition.
- :class:`SimpleExtractor` — a base class with sensible defaults for
  function-based extractors.
- Type-helper factory functions for creating each entity type.

These tools are intended for third-party developers building custom
extractors that plug into the Kutana AI extraction pipeline.

Example — decorator style::

    from kutana_core.extraction.sdk import extractor, make_task

    @extractor(name="action-items", entity_types=["task"])
    async def extract_actions(batch: TranscriptBatch) -> ExtractionResult:
        entities = []
        for seg in batch.segments:
            if "action" in seg.text.lower():
                entities.append(make_task(
                    batch,
                    title=seg.text[:80],
                    source_segment_id=seg.segment_id,
                ))
        return ExtractionResult(
            batch_id=batch.batch_id,
            entities=entities,
            processing_time_ms=0.0,
        )

Example — class style::

    from kutana_core.extraction.sdk import SimpleExtractor, make_task

    class ActionItemExtractor(SimpleExtractor):
        name = "action-items"
        entity_types = ["task"]

        async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
            ...
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from kutana_core.extraction.abc import Extractor
from kutana_core.extraction.types import (
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

# ---------------------------------------------------------------------------
# SimpleExtractor base class
# ---------------------------------------------------------------------------


class SimpleExtractor(Extractor):
    """Base class for custom extractors with class-attribute configuration.

    Subclass this and set ``name`` and ``entity_types`` as class attributes,
    then override :meth:`extract`.

    Example::

        class ComplianceExtractor(SimpleExtractor):
            name = "compliance"
            entity_types = ["compliance_mention"]

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                ...

    Attributes:
        name: Set this class attribute to the unique extractor name.
        entity_types: Set this class attribute to a list of entity type strings.
    """

    #: Override in subclasses to set the unique extractor name.
    name: ClassVar[str] = ""
    #: Override in subclasses to list the entity types this extractor produces.
    entity_types: ClassVar[list[str]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate that subclasses set non-empty name and entity_types."""
        super().__init_subclass__(**kwargs)
        # Only validate concrete (non-abstract) subclasses
        abstract_methods: frozenset[str] = getattr(cls, "__abstractmethods__", frozenset())
        if not abstract_methods:
            if not cls.name:
                import warnings

                warnings.warn(
                    f"{cls.__name__}.name is empty — set it to a unique identifier.",
                    stacklevel=2,
                )
            if not cls.entity_types:
                import warnings

                warnings.warn(
                    f"{cls.__name__}.entity_types is empty — set it to the list of "
                    "entity types this extractor produces.",
                    stacklevel=2,
                )

    async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
        """Extract entities from a transcript batch.

        Override this method in your subclass.

        Args:
            batch: The windowed transcript batch to process.

        Returns:
            An :class:`~kutana_core.extraction.types.ExtractionResult`.
        """
        return ExtractionResult(
            batch_id=batch.batch_id,
            entities=[],
            processing_time_ms=0.0,
        )

    def timed_result(
        self,
        batch: TranscriptBatch,
        entities: list[Any],
        start: float,
    ) -> ExtractionResult:
        """Build an ExtractionResult with wall-clock processing time.

        Args:
            batch: The batch that was processed.
            entities: List of extracted entities.
            start: ``time.monotonic()`` value recorded before extraction.

        Returns:
            An :class:`~kutana_core.extraction.types.ExtractionResult`.
        """
        return ExtractionResult(
            batch_id=batch.batch_id,
            entities=entities,
            processing_time_ms=(time.monotonic() - start) * 1000.0,
        )


# ---------------------------------------------------------------------------
# @extractor decorator
# ---------------------------------------------------------------------------


class _FunctionExtractor(Extractor):
    """Internal Extractor implementation wrapping an async function."""

    def __init__(
        self,
        fn: Any,
        extractor_name: str,
        extractor_entity_types: list[str],
    ) -> None:
        self._fn = fn
        self._name = extractor_name
        self._entity_types = extractor_entity_types

    @property
    def name(self) -> str:
        """Return the extractor name set by the @extractor decorator."""
        return self._name

    @property
    def entity_types(self) -> list[str]:
        """Return the entity types set by the @extractor decorator."""
        return list(self._entity_types)

    async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
        """Delegate extraction to the wrapped async function."""
        result: ExtractionResult = await self._fn(batch)
        return result


def extractor(
    name: str,
    entity_types: list[str],
) -> Any:
    """Class decorator that turns an async function into an :class:`Extractor`.

    The decorated function must accept a single
    :class:`~kutana_core.extraction.types.TranscriptBatch` argument and
    return an :class:`~kutana_core.extraction.types.ExtractionResult`.

    Args:
        name: Unique extractor identifier used in logging and topic routing.
        entity_types: List of entity type strings this extractor can produce.

    Returns:
        A decorator that wraps the function in a :class:`_FunctionExtractor`.

    Example::

        @extractor(name="sentiment", entity_types=["key_point"])
        async def sentiment_extractor(batch: TranscriptBatch) -> ExtractionResult:
            ...

        # sentiment_extractor is now an Extractor instance
        result = await sentiment_extractor.extract(batch)
    """
    if not name:
        msg = "@extractor requires a non-empty name"
        raise ValueError(msg)
    if not entity_types:
        msg = "@extractor requires a non-empty entity_types list"
        raise ValueError(msg)

    def decorator(fn: Any) -> _FunctionExtractor:
        instance = _FunctionExtractor(
            fn=fn,
            extractor_name=name,
            extractor_entity_types=entity_types,
        )
        # Copy docstring and module from the wrapped function
        instance.__doc__ = fn.__doc__
        return instance

    return decorator


# ---------------------------------------------------------------------------
# Entity factory helpers
# ---------------------------------------------------------------------------


def make_task(
    batch: TranscriptBatch,
    title: str,
    *,
    assignee: str | None = None,
    deadline: str | None = None,
    priority: str = "medium",
    status: str = "identified",
    source_speaker: str | None = None,
    source_segment_id: str | None = None,
    confidence: float = 0.85,
) -> TaskEntity:
    """Create a :class:`~kutana_core.extraction.types.TaskEntity`.

    Args:
        batch: The batch being processed (provides meeting_id and batch_id).
        title: Clear, actionable task description.
        assignee: Name of the person assigned, if known.
        deadline: Deadline string as mentioned in the transcript.
        priority: Task priority (``"high"``, ``"medium"``, or ``"low"``).
        status: Task status (``"identified"``, ``"accepted"``, or ``"completed"``).
        source_speaker: Speaker who stated the task.
        source_segment_id: ID of the source segment.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`TaskEntity`.
    """
    return TaskEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        title=title,
        assignee=assignee,
        deadline=deadline,
        priority=priority,
        status=status,
        source_speaker=source_speaker,
        source_segment_id=source_segment_id,
        confidence=confidence,
    )


def make_decision(
    batch: TranscriptBatch,
    summary: str,
    *,
    participants: list[str] | None = None,
    rationale: str = "",
    source_segment_ids: list[str] | None = None,
    confidence: float = 0.80,
) -> DecisionEntity:
    """Create a :class:`~kutana_core.extraction.types.DecisionEntity`.

    Args:
        batch: The batch being processed.
        summary: Concise description of what was decided.
        participants: Names of participants involved.
        rationale: Reasoning behind the decision.
        source_segment_ids: Segment IDs supporting this decision.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`DecisionEntity`.
    """
    return DecisionEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        summary=summary,
        participants=participants or [],
        rationale=rationale,
        source_segment_ids=source_segment_ids or [],
        confidence=confidence,
    )


def make_question(
    batch: TranscriptBatch,
    text: str,
    *,
    asker: str | None = None,
    status: str = "open",
    answer: str | None = None,
    source_segment_id: str | None = None,
    confidence: float = 0.85,
) -> QuestionEntity:
    """Create a :class:`~kutana_core.extraction.types.QuestionEntity`.

    Args:
        batch: The batch being processed.
        text: The question text.
        asker: Name of the person who asked.
        status: ``"open"`` or ``"answered"``.
        answer: The answer given, if resolved.
        source_segment_id: ID of the source segment.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`QuestionEntity`.
    """
    return QuestionEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        text=text,
        asker=asker,
        status=status,
        answer=answer,
        source_segment_id=source_segment_id,
        confidence=confidence,
    )


def make_key_point(
    batch: TranscriptBatch,
    summary: str,
    *,
    speaker: str | None = None,
    topic: str = "",
    importance: str = "medium",
    source_segment_id: str | None = None,
    confidence: float = 0.85,
) -> KeyPointEntity:
    """Create a :class:`~kutana_core.extraction.types.KeyPointEntity`.

    Args:
        batch: The batch being processed.
        summary: The key point as a concise statement.
        speaker: Speaker who made the point.
        topic: Topic or theme this point belongs to.
        importance: ``"high"``, ``"medium"``, or ``"low"``.
        source_segment_id: ID of the source segment.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`KeyPointEntity`.
    """
    return KeyPointEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        summary=summary,
        speaker=speaker,
        topic=topic,
        importance=importance,
        source_segment_id=source_segment_id,
        confidence=confidence,
    )


def make_blocker(
    batch: TranscriptBatch,
    description: str,
    *,
    owner: str | None = None,
    severity: str = "medium",
    related_tasks: list[str] | None = None,
    source_segment_id: str | None = None,
    confidence: float = 0.90,
) -> BlockerEntity:
    """Create a :class:`~kutana_core.extraction.types.BlockerEntity`.

    Args:
        batch: The batch being processed.
        description: Clear description of the blocker.
        owner: Person responsible for resolving it.
        severity: ``"critical"``, ``"high"``, ``"medium"``, or ``"low"``.
        related_tasks: Titles or IDs of affected tasks.
        source_segment_id: ID of the source segment.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`BlockerEntity`.
    """
    return BlockerEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        description=description,
        owner=owner,
        severity=severity,
        related_tasks=related_tasks or [],
        source_segment_id=source_segment_id,
        confidence=confidence,
    )


def make_follow_up(
    batch: TranscriptBatch,
    description: str,
    *,
    owner: str | None = None,
    due_context: str | None = None,
    source_segment_id: str | None = None,
    confidence: float = 0.85,
) -> FollowUpEntity:
    """Create a :class:`~kutana_core.extraction.types.FollowUpEntity`.

    Args:
        batch: The batch being processed.
        description: What needs to be followed up on.
        owner: Person responsible for the follow-up.
        due_context: Timing or deadline context from the transcript.
        source_segment_id: ID of the source segment.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`FollowUpEntity`.
    """
    return FollowUpEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        description=description,
        owner=owner,
        due_context=due_context,
        source_segment_id=source_segment_id,
        confidence=confidence,
    )


def make_entity_mention(
    batch: TranscriptBatch,
    name: str,
    kind: str,
    *,
    context: str = "",
    first_mention_segment_id: str | None = None,
    confidence: float = 0.90,
) -> EntityMentionEntity:
    """Create an :class:`~kutana_core.extraction.types.EntityMentionEntity`.

    Args:
        batch: The batch being processed.
        name: The canonical name of the mentioned entity.
        kind: Entity category: ``"person"``, ``"system"``, ``"concept"``,
            or ``"org"``.
        context: Brief context around the first mention.
        first_mention_segment_id: ID of the segment containing the first mention.
        confidence: Extraction confidence (0.0-1.0).

    Returns:
        A validated :class:`EntityMentionEntity`.
    """
    return EntityMentionEntity(
        meeting_id=batch.meeting_id,
        batch_id=batch.batch_id,
        name=name,
        kind=kind,
        context=context,
        first_mention_segment_id=first_mention_segment_id,
        confidence=confidence,
    )
