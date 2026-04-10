"""Event definitions for inter-service communication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from kutana_core.models.decision import Decision  # noqa: TC001
from kutana_core.models.task import Task, TaskStatus  # noqa: TC001
from kutana_core.models.transcript import TranscriptSegment  # noqa: TC001


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


class AgentSessionWarmed(BaseEvent):
    """Emitted when a background-warmed managed agent reaches idle.

    Flows through the agent gateway → frontend WebSocket so the per-agent
    spinner can transition from ``warming`` → ``ready``.

    Attributes:
        meeting_id: Meeting the agent was warmed for.
        template_id: Agent template that was activated.
        hosted_session_id: The newly-created ``HostedAgentSessionORM`` row ID.
    """

    event_type: ClassVar[str] = "agent.session.warmed"
    meeting_id: UUID
    template_id: UUID
    hosted_session_id: UUID


class AgentSessionFailed(BaseEvent):
    """Emitted when a background-warmed managed agent fails to activate.

    Flows through the agent gateway → frontend WebSocket so the per-agent
    spinner can transition to ``failed`` with a retry affordance.

    Attributes:
        meeting_id: Meeting the agent was being warmed for.
        template_id: Agent template whose activation failed.
        error: Human-readable error detail.
    """

    event_type: ClassVar[str] = "agent.session.failed"
    meeting_id: UUID
    template_id: UUID
    error: str


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
        capabilities: Granted capabilities (e.g. listen, speak, voice).
        audio_capability: High-level audio capability declaration
            (text_only, tts_enabled, voice).
    """

    event_type: ClassVar[str] = "participant.joined"
    participant_id: UUID
    meeting_id: UUID
    name: str
    role: str
    connection_type: str | None = None
    capabilities: list[str] | None = None
    audio_capability: str | None = None


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


# ---------------------------------------------------------------------------
# Turn management events (Phase 3: Turn Management Infrastructure)
# ---------------------------------------------------------------------------


class HandRaised(BaseEvent):
    """Emitted when a participant raises their hand to speak.

    Attributes:
        meeting_id: ID of the meeting.
        participant_id: ID of the participant who raised their hand.
        hand_raise_id: Unique identifier for this hand raise event.
        queue_position: 1-based position in queue; 0 means immediately promoted.
        priority: Queue priority — "normal" or "urgent".
        topic: Optional topic the participant wants to discuss.
    """

    event_type: ClassVar[str] = "turn.hand.raised"
    meeting_id: UUID
    participant_id: UUID
    hand_raise_id: UUID
    queue_position: int
    priority: str = "normal"
    topic: str | None = None


class SpeakerChanged(BaseEvent):
    """Emitted when the active speaker changes.

    Attributes:
        meeting_id: ID of the meeting.
        previous_speaker_id: ID of the outgoing speaker (None if no previous speaker).
        new_speaker_id: ID of the incoming speaker (None if queue is now empty).
    """

    event_type: ClassVar[str] = "turn.speaker.changed"
    meeting_id: UUID
    previous_speaker_id: UUID | None = None
    new_speaker_id: UUID | None = None


class QueueUpdated(BaseEvent):
    """Emitted when the speaker queue order changes.

    Attributes:
        meeting_id: ID of the meeting.
        active_speaker_id: Current active speaker (None if no one is speaking).
        queue: Ordered list of queue entry dicts (position, participant_id, priority, topic).
    """

    event_type: ClassVar[str] = "turn.queue.updated"
    meeting_id: UUID
    active_speaker_id: UUID | None = None
    queue: list[dict[str, Any]] = []


class FinishedSpeaking(BaseEvent):
    """Emitted when a participant finishes their speaking turn.

    Attributes:
        meeting_id: ID of the meeting.
        participant_id: ID of the participant who finished speaking.
    """

    event_type: ClassVar[str] = "turn.speaker.finished"
    meeting_id: UUID
    participant_id: UUID


class YourTurn(BaseEvent):
    """Targeted notification sent to the participant who is next to speak.

    Attributes:
        meeting_id: ID of the meeting.
        participant_id: ID of the participant whose turn it is.
    """

    event_type: ClassVar[str] = "turn.your_turn"
    meeting_id: UUID
    participant_id: UUID


# ---------------------------------------------------------------------------
# Feed events (Kutana Feeds — bidirectional integration layer)
# ---------------------------------------------------------------------------


class FeedCreated(BaseEvent):
    """Emitted when a new feed configuration is created.

    Attributes:
        feed_id: ID of the newly created feed.
        user_id: ID of the user who created the feed.
        platform: Target platform.
        direction: Feed direction.
    """

    event_type: ClassVar[str] = "feed.created"
    feed_id: UUID
    user_id: UUID
    platform: str
    direction: str


class FeedUpdated(BaseEvent):
    """Emitted when a feed configuration is updated.

    Attributes:
        feed_id: ID of the updated feed.
        user_id: ID of the feed owner.
    """

    event_type: ClassVar[str] = "feed.updated"
    feed_id: UUID
    user_id: UUID


class FeedDeleted(BaseEvent):
    """Emitted when a feed configuration is deleted.

    Attributes:
        feed_id: ID of the deleted feed.
        user_id: ID of the feed owner.
    """

    event_type: ClassVar[str] = "feed.deleted"
    feed_id: UUID
    user_id: UUID


class FeedRunStarted(BaseEvent):
    """Emitted when a feed run begins execution.

    Attributes:
        feed_run_id: ID of the feed run.
        feed_id: ID of the parent feed.
        meeting_id: Meeting being processed.
        direction: Run direction (inbound or outbound).
    """

    event_type: ClassVar[str] = "feed.run.started"
    feed_run_id: UUID
    feed_id: UUID
    meeting_id: UUID
    direction: str


class FeedRunCompleted(BaseEvent):
    """Emitted when a feed run completes successfully.

    Attributes:
        feed_run_id: ID of the feed run.
        feed_id: ID of the parent feed.
        meeting_id: Meeting that was processed.
        direction: Run direction.
    """

    event_type: ClassVar[str] = "feed.run.completed"
    feed_run_id: UUID
    feed_id: UUID
    meeting_id: UUID
    direction: str


class FeedRunFailed(BaseEvent):
    """Emitted when a feed run fails after all retries.

    Attributes:
        feed_run_id: ID of the feed run.
        feed_id: ID of the parent feed.
        meeting_id: Meeting that was being processed.
        direction: Run direction.
        error: Error message describing the failure.
    """

    event_type: ClassVar[str] = "feed.run.failed"
    feed_run_id: UUID
    feed_id: UUID
    meeting_id: UUID
    direction: str
    error: str


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
HandRaised.model_rebuild()
SpeakerChanged.model_rebuild()
QueueUpdated.model_rebuild()
FinishedSpeaking.model_rebuild()
YourTurn.model_rebuild()
FeedCreated.model_rebuild()
FeedUpdated.model_rebuild()
FeedDeleted.model_rebuild()
FeedRunStarted.model_rebuild()
FeedRunCompleted.model_rebuild()
FeedRunFailed.model_rebuild()
