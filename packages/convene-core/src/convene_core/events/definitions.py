"""Event definitions for inter-service communication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from convene_core.models.decision import Decision  # noqa: TC001
from convene_core.models.task import Task, TaskStatus  # noqa: TC001
from convene_core.models.transcript import TranscriptSegment  # noqa: TC001


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class BaseEvent(BaseModel):
    """Base class for all domain events.

    Attributes:
        event_id: Unique identifier for this event instance.
        timestamp: When the event was created (UTC).
    """

    event_id: UUID = Field(default_factory=uuid4)
    event_type: ClassVar[str] = "base_event"
    timestamp: datetime = Field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary including event_type.

        Returns:
            Dictionary representation of the event with event_type field.
        """
        data = self.model_dump(mode="json")
        data["event_type"] = self.event_type
        return data


class MeetingStarted(BaseEvent):
    """Emitted when a meeting begins.

    Attributes:
        meeting_id: ID of the meeting that started.
    """

    event_type: ClassVar[str] = "meeting.started"
    meeting_id: UUID


class MeetingEnded(BaseEvent):
    """Emitted when a meeting ends.

    Attributes:
        meeting_id: ID of the meeting that ended.
    """

    event_type: ClassVar[str] = "meeting.ended"
    meeting_id: UUID


class TranscriptSegmentFinal(BaseEvent):
    """Emitted when a final transcript segment is available.

    Attributes:
        meeting_id: ID of the meeting the segment belongs to.
        segment: The finalized transcript segment.
    """

    event_type: ClassVar[str] = "transcript.segment.final"
    meeting_id: UUID
    segment: TranscriptSegment


class TaskCreated(BaseEvent):
    """Emitted when a new task is extracted from a meeting.

    Attributes:
        task: The newly created task.
    """

    event_type: ClassVar[str] = "task.created"
    task: Task


class TaskUpdated(BaseEvent):
    """Emitted when an existing task is updated.

    Attributes:
        task: The updated task.
        previous_status: The status before the update.
    """

    event_type: ClassVar[str] = "task.updated"
    task: Task
    previous_status: TaskStatus


class DecisionRecorded(BaseEvent):
    """Emitted when a decision is recorded during a meeting.

    Attributes:
        decision: The recorded decision.
    """

    event_type: ClassVar[str] = "decision.recorded"
    decision: Decision


# ---------------------------------------------------------------------------
# Room and agent events (Phase P-A: Agent Gateway)
# ---------------------------------------------------------------------------


class RoomCreated(BaseEvent):
    """Emitted when a meeting room is created.

    Attributes:
        room_id: ID of the newly created room.
        room_name: Human-readable room name.
        meeting_id: Associated meeting ID (if any).
    """

    event_type: ClassVar[str] = "room.created"
    room_id: UUID
    room_name: str
    meeting_id: UUID | None = None


class AgentJoined(BaseEvent):
    """Emitted when an AI agent joins a meeting.

    Attributes:
        agent_config_id: ID of the agent configuration.
        meeting_id: ID of the meeting joined.
        room_name: Room the agent joined.
        capabilities: Capabilities granted to the agent.
    """

    event_type: ClassVar[str] = "agent.joined"
    agent_config_id: UUID
    meeting_id: UUID
    room_name: str
    capabilities: list[str]


class AgentLeft(BaseEvent):
    """Emitted when an AI agent leaves a meeting.

    Attributes:
        agent_config_id: ID of the agent configuration.
        meeting_id: ID of the meeting left.
        room_name: Room the agent left.
        reason: Reason for leaving.
    """

    event_type: ClassVar[str] = "agent.left"
    agent_config_id: UUID
    meeting_id: UUID
    room_name: str
    reason: str = "normal"


class ParticipantJoined(BaseEvent):
    """Emitted when a participant joins a meeting.

    Attributes:
        participant_id: ID of the participant.
        meeting_id: ID of the meeting joined.
        name: Display name of the participant.
        role: Participant role.
        connection_type: How the participant is connected.
    """

    event_type: ClassVar[str] = "participant.joined"
    participant_id: UUID
    meeting_id: UUID
    name: str
    role: str
    connection_type: str | None = None


class ParticipantLeft(BaseEvent):
    """Emitted when a participant leaves a meeting.

    Attributes:
        participant_id: ID of the participant.
        meeting_id: ID of the meeting left.
        reason: Reason for leaving.
    """

    event_type: ClassVar[str] = "participant.left"
    participant_id: UUID
    meeting_id: UUID
    reason: str = "normal"


class AgentData(BaseEvent):
    """Emitted when an agent sends structured data.

    Attributes:
        agent_config_id: ID of the agent configuration.
        meeting_id: ID of the meeting.
        channel: Data channel name.
        payload: Arbitrary data payload.
    """

    event_type: ClassVar[str] = "agent.data"
    agent_config_id: UUID
    meeting_id: UUID
    channel: str
    payload: dict[str, object]


# Rebuild models to resolve forward references from __future__ annotations
TranscriptSegmentFinal.model_rebuild()
TaskCreated.model_rebuild()
TaskUpdated.model_rebuild()
DecisionRecorded.model_rebuild()
RoomCreated.model_rebuild()
AgentJoined.model_rebuild()
AgentLeft.model_rebuild()
ParticipantJoined.model_rebuild()
ParticipantLeft.model_rebuild()
AgentData.model_rebuild()
