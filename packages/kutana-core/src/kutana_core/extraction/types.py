"""Entity schema for the Meeting Insight Stream extraction pipeline.

Defines seven entity types extracted from meeting transcript batches, plus
batch and result container models.  All entity types share a common
``ExtractedEntity`` base and are combined into a Pydantic v2 discriminated
union (``AnyExtractedEntity``) for type-safe serialization and validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


def _new_id() -> str:
    """Return a new UUID string."""
    return str(uuid4())


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    """Base model shared by all extracted entity types.

    Attributes:
        id: Auto-generated UUID string for this entity instance.
        entity_type: Discriminator field used to select the concrete subtype.
        meeting_id: ID of the meeting this entity belongs to.
        confidence: Extractor confidence score (0.0 - 1.0).
        extracted_at: UTC timestamp when the entity was extracted.
        batch_id: ID of the ``TranscriptBatch`` that produced this entity.
    """

    id: str = Field(default_factory=_new_id)
    entity_type: str
    meeting_id: str
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=_utc_now)
    batch_id: str

    def content_key(self) -> str:
        """Return the primary content string used for deduplication.

        Subclasses should override this to return their main text field.
        """
        return ""


# ---------------------------------------------------------------------------
# Concrete entity types
# ---------------------------------------------------------------------------


class TaskEntity(ExtractedEntity):
    """An action item or commitment identified in the transcript.

    Attributes:
        title: Clear, actionable task description.
        assignee: Name of the person assigned, if mentioned.
        deadline: Deadline or due date string as mentioned in transcript.
        priority: Task urgency level.
        status: Current lifecycle state.
        source_speaker: Speaker who stated or accepted the task.
        source_segment_id: ID of the segment where the task was identified.
    """

    entity_type: Literal["task"] = "task"
    title: str
    assignee: str | None = None
    deadline: str | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["identified", "accepted", "completed"] = "identified"
    source_speaker: str | None = None
    source_segment_id: str | None = None

    def content_key(self) -> str:
        """Return normalized title for deduplication."""
        return self.title.lower().strip()


class DecisionEntity(ExtractedEntity):
    """A decision made during the meeting.

    Attributes:
        summary: Concise description of what was decided.
        participants: Names of participants involved in making the decision.
        rationale: Reasoning behind the decision, if stated.
        source_segment_ids: IDs of segments supporting this decision.
    """

    entity_type: Literal["decision"] = "decision"
    summary: str
    participants: list[str] = Field(default_factory=list)
    rationale: str = ""
    source_segment_ids: list[str] = Field(default_factory=list)

    def content_key(self) -> str:
        """Return normalized summary for deduplication."""
        return self.summary.lower().strip()


class QuestionEntity(ExtractedEntity):
    """A question raised during the meeting.

    Attributes:
        text: The question text as asked.
        asker: Name of the person who asked the question.
        status: Whether the question has been answered.
        answer: The answer given, if the question was resolved.
        source_segment_id: ID of the segment containing this question.
    """

    entity_type: Literal["question"] = "question"
    text: str
    asker: str | None = None
    status: Literal["open", "answered"] = "open"
    answer: str | None = None
    source_segment_id: str | None = None

    def content_key(self) -> str:
        """Return normalized question text for deduplication."""
        return self.text.lower().strip()


class EntityMentionEntity(ExtractedEntity):
    """A named entity (person, system, concept, or org) mentioned in the meeting.

    Attributes:
        name: The canonical name of the mentioned entity.
        kind: The category of entity (person, system, concept, or org).
        context: A brief snippet of context around the first mention.
        first_mention_segment_id: ID of the segment containing the first mention.
    """

    entity_type: Literal["entity_mention"] = "entity_mention"
    name: str
    kind: Literal["person", "system", "concept", "org"]
    context: str = ""
    first_mention_segment_id: str | None = None

    def content_key(self) -> str:
        """Return normalized name+kind for deduplication."""
        return f"{self.name.lower().strip()}:{self.kind}"


class KeyPointEntity(ExtractedEntity):
    """A significant point or insight from the meeting discussion.

    Attributes:
        summary: The key point as a concise statement.
        speaker: Name of the speaker who made the point.
        topic: The topic or theme this point belongs to.
        importance: Relative importance of this point.
        source_segment_id: ID of the segment where this was stated.
    """

    entity_type: Literal["key_point"] = "key_point"
    summary: str
    speaker: str | None = None
    topic: str = ""
    importance: Literal["high", "medium", "low"] = "medium"
    source_segment_id: str | None = None

    def content_key(self) -> str:
        """Return normalized summary for deduplication."""
        return self.summary.lower().strip()


class BlockerEntity(ExtractedEntity):
    """An impediment or blocker raised during the meeting.

    Attributes:
        description: Clear description of the blocker.
        owner: Person responsible for resolving it.
        severity: How critical this blocker is.
        related_tasks: IDs or titles of tasks affected by this blocker.
        source_segment_id: ID of the segment where this was mentioned.
    """

    entity_type: Literal["blocker"] = "blocker"
    description: str
    owner: str | None = None
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    related_tasks: list[str] = Field(default_factory=list)
    source_segment_id: str | None = None

    def content_key(self) -> str:
        """Return normalized description for deduplication."""
        return self.description.lower().strip()


class FollowUpEntity(ExtractedEntity):
    """A follow-up item that should be actioned after the meeting.

    Attributes:
        description: What needs to be followed up on.
        owner: Person responsible for the follow-up.
        due_context: Timing or deadline context as mentioned in the transcript.
        source_segment_id: ID of the segment where this was mentioned.
    """

    entity_type: Literal["follow_up"] = "follow_up"
    description: str
    owner: str | None = None
    due_context: str | None = None
    source_segment_id: str | None = None

    def content_key(self) -> str:
        """Return normalized description for deduplication."""
        return self.description.lower().strip()


# ---------------------------------------------------------------------------
# Discriminated union covering all entity types
# ---------------------------------------------------------------------------

#: Annotated union for use as a Pydantic field type.  Pydantic uses the
#: ``entity_type`` literal to select the correct submodel during validation.
AnyExtractedEntity = Annotated[
    TaskEntity
    | DecisionEntity
    | QuestionEntity
    | EntityMentionEntity
    | KeyPointEntity
    | BlockerEntity
    | FollowUpEntity,
    Field(discriminator="entity_type"),
]


# ---------------------------------------------------------------------------
# Batch and result containers
# ---------------------------------------------------------------------------


class BatchSegment(BaseModel):
    """A single transcript segment included in an extraction batch.

    Attributes:
        segment_id: ID of the originating ``TranscriptSegment``.
        speaker: Speaker identifier or display name, if available.
        text: Transcribed text of this segment.
        start_time: Start time in seconds from meeting start.
        end_time: End time in seconds from meeting start.
    """

    segment_id: str
    speaker: str | None = None
    text: str
    start_time: float
    end_time: float


class TranscriptBatch(BaseModel):
    """A windowed collection of transcript segments for entity extraction.

    Attributes:
        batch_id: Auto-generated UUID identifying this batch.
        meeting_id: ID of the meeting these segments belong to.
        segments: The transcript segments in this batch window.
        context_segments: Segments from the previous batch for continuity.
        batch_window_seconds: Duration of the batch window in seconds.
    """

    batch_id: str = Field(default_factory=_new_id)
    meeting_id: str
    segments: list[BatchSegment]
    context_segments: list[BatchSegment] = Field(default_factory=list)
    batch_window_seconds: float = 30.0


class ExtractionResult(BaseModel):
    """Result returned by an ``Extractor`` after processing a batch.

    Attributes:
        batch_id: ID of the batch that was processed.
        entities: All entities extracted from this batch.
        processing_time_ms: Wall-clock time taken by the extractor (ms).
    """

    batch_id: str
    entities: list[AnyExtractedEntity]
    processing_time_ms: float
