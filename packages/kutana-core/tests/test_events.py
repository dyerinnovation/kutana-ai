"""Tests for Kutana AI event definitions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from kutana_core.events.definitions import (
    AgentData,
    AgentJoined,
    AgentLeft,
    BaseEvent,
    DecisionRecorded,
    MeetingEnded,
    MeetingStarted,
    ParticipantJoined,
    ParticipantLeft,
    RoomCreated,
    TaskCreated,
    TaskUpdated,
    TranscriptSegmentFinal,
)
from kutana_core.models.decision import Decision
from kutana_core.models.task import Task, TaskPriority, TaskStatus
from kutana_core.models.transcript import TranscriptSegment

MEETING_ID = uuid4()
PARTICIPANT_ID = uuid4()


class TestBaseEvent:
    """Tests for the BaseEvent base class."""

    def test_base_event_defaults(self) -> None:
        """BaseEvent generates event_id and timestamp automatically."""
        event = BaseEvent()
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_base_event_to_dict_includes_event_type(self) -> None:
        """to_dict() includes the event_type class variable."""
        event = BaseEvent()
        data = event.to_dict()
        assert "event_type" in data
        assert data["event_type"] == "base_event"
        assert "event_id" in data
        assert "timestamp" in data


class TestMeetingStarted:
    """Tests for the MeetingStarted event."""

    def test_meeting_started_creation(self) -> None:
        """MeetingStarted event can be created with meeting_id."""
        event = MeetingStarted(meeting_id=MEETING_ID)
        assert event.meeting_id == MEETING_ID
        assert isinstance(event.event_id, UUID)

    def test_meeting_started_event_type(self) -> None:
        """MeetingStarted has correct event_type."""
        event = MeetingStarted(meeting_id=MEETING_ID)
        assert event.to_dict()["event_type"] == "meeting.started"

    def test_meeting_started_to_dict(self) -> None:
        """MeetingStarted to_dict includes meeting_id."""
        event = MeetingStarted(meeting_id=MEETING_ID)
        data = event.to_dict()
        assert data["meeting_id"] == str(MEETING_ID)
        assert data["event_type"] == "meeting.started"


class TestMeetingEnded:
    """Tests for the MeetingEnded event."""

    def test_meeting_ended_creation(self) -> None:
        """MeetingEnded event can be created with meeting_id."""
        event = MeetingEnded(meeting_id=MEETING_ID)
        assert event.meeting_id == MEETING_ID

    def test_meeting_ended_event_type(self) -> None:
        """MeetingEnded has correct event_type."""
        event = MeetingEnded(meeting_id=MEETING_ID)
        assert event.to_dict()["event_type"] == "meeting.ended"


class TestTranscriptSegmentFinal:
    """Tests for the TranscriptSegmentFinal event."""

    def test_creation_with_segment(self) -> None:
        """TranscriptSegmentFinal wraps a TranscriptSegment."""
        segment = TranscriptSegment(
            meeting_id=MEETING_ID,
            speaker_id="spk_001",
            text="We need to ship by Friday",
            start_time=120.0,
            end_time=125.5,
            confidence=0.92,
        )
        event = TranscriptSegmentFinal(
            meeting_id=MEETING_ID,
            segment=segment,
        )
        assert event.segment.text == "We need to ship by Friday"
        assert event.meeting_id == MEETING_ID

    def test_event_type(self) -> None:
        """TranscriptSegmentFinal has correct event_type."""
        segment = TranscriptSegment(
            meeting_id=MEETING_ID,
            text="test",
            start_time=0.0,
            end_time=1.0,
        )
        event = TranscriptSegmentFinal(
            meeting_id=MEETING_ID,
            segment=segment,
        )
        assert event.to_dict()["event_type"] == "transcript.segment.final"

    def test_nested_serialization(self) -> None:
        """to_dict() correctly serializes nested TranscriptSegment."""
        segment = TranscriptSegment(
            meeting_id=MEETING_ID,
            speaker_id="spk_002",
            text="Let's discuss the roadmap",
            start_time=10.0,
            end_time=14.0,
            confidence=0.88,
        )
        event = TranscriptSegmentFinal(
            meeting_id=MEETING_ID,
            segment=segment,
        )
        data = event.to_dict()
        assert "segment" in data
        assert data["segment"]["text"] == "Let's discuss the roadmap"
        assert data["segment"]["speaker_id"] == "spk_002"
        assert data["segment"]["confidence"] == 0.88


class TestTaskCreated:
    """Tests for the TaskCreated event."""

    def test_task_created_event(self) -> None:
        """TaskCreated event wraps a Task."""
        task = Task(
            meeting_id=MEETING_ID,
            description="Update documentation",
            priority=TaskPriority.HIGH,
        )
        event = TaskCreated(task=task)
        assert event.task.description == "Update documentation"
        assert event.to_dict()["event_type"] == "task.created"

    def test_task_created_serialization(self) -> None:
        """TaskCreated to_dict includes full task data."""
        task = Task(
            meeting_id=MEETING_ID,
            description="Fix the bug",
            assignee_id=PARTICIPANT_ID,
        )
        event = TaskCreated(task=task)
        data = event.to_dict()
        assert data["task"]["description"] == "Fix the bug"
        assert data["task"]["assignee_id"] == str(PARTICIPANT_ID)


class TestTaskUpdated:
    """Tests for the TaskUpdated event."""

    def test_task_updated_event(self) -> None:
        """TaskUpdated event tracks previous status."""
        task = Task(
            meeting_id=MEETING_ID,
            description="Deploy v2",
            status=TaskStatus.IN_PROGRESS,
        )
        event = TaskUpdated(
            task=task,
            previous_status=TaskStatus.PENDING,
        )
        assert event.task.status == TaskStatus.IN_PROGRESS
        assert event.previous_status == TaskStatus.PENDING
        assert event.to_dict()["event_type"] == "task.updated"

    def test_task_updated_serialization(self) -> None:
        """TaskUpdated to_dict includes both task and previous_status."""
        task = Task(
            meeting_id=MEETING_ID,
            description="Review PR",
            status=TaskStatus.DONE,
        )
        event = TaskUpdated(
            task=task,
            previous_status=TaskStatus.IN_PROGRESS,
        )
        data = event.to_dict()
        assert data["previous_status"] == "in_progress"
        assert data["task"]["status"] == "done"


class TestDecisionRecorded:
    """Tests for the DecisionRecorded event."""

    def test_decision_recorded_event(self) -> None:
        """DecisionRecorded event wraps a Decision."""
        decision = Decision(
            meeting_id=MEETING_ID,
            description="Use PostgreSQL",
            decided_by_id=PARTICIPANT_ID,
        )
        event = DecisionRecorded(decision=decision)
        assert event.decision.description == "Use PostgreSQL"
        assert event.to_dict()["event_type"] == "decision.recorded"

    def test_decision_recorded_serialization(self) -> None:
        """DecisionRecorded to_dict includes full decision data."""
        p1, p2 = uuid4(), uuid4()
        decision = Decision(
            meeting_id=MEETING_ID,
            description="Migrate to AWS",
            decided_by_id=PARTICIPANT_ID,
            participants_present=[p1, p2],
        )
        event = DecisionRecorded(decision=decision)
        data = event.to_dict()
        assert data["decision"]["description"] == "Migrate to AWS"
        assert len(data["decision"]["participants_present"]) == 2


# ---- Room and Agent Events (Phase P-A) ----


AGENT_CONFIG_ID = uuid4()
ROOM_ID = uuid4()


class TestRoomCreated:
    """Tests for the RoomCreated event."""

    def test_room_created_event(self) -> None:
        """RoomCreated event can be created."""
        event = RoomCreated(
            room_id=ROOM_ID,
            room_name="sprint-room",
            meeting_id=MEETING_ID,
        )
        assert event.room_id == ROOM_ID
        assert event.room_name == "sprint-room"
        assert event.meeting_id == MEETING_ID

    def test_room_created_event_type(self) -> None:
        """RoomCreated has correct event_type."""
        event = RoomCreated(room_id=ROOM_ID, room_name="test")
        assert event.to_dict()["event_type"] == "room.created"

    def test_room_created_optional_meeting_id(self) -> None:
        """RoomCreated meeting_id is optional."""
        event = RoomCreated(room_id=ROOM_ID, room_name="adhoc")
        assert event.meeting_id is None


class TestAgentJoined:
    """Tests for the AgentJoined event."""

    def test_agent_joined_event(self) -> None:
        """AgentJoined event can be created."""
        event = AgentJoined(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            room_name="sprint-room",
            capabilities=["listen", "transcribe"],
        )
        assert event.agent_config_id == AGENT_CONFIG_ID
        assert event.capabilities == ["listen", "transcribe"]

    def test_agent_joined_event_type(self) -> None:
        """AgentJoined has correct event_type."""
        event = AgentJoined(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            room_name="test",
            capabilities=[],
        )
        assert event.to_dict()["event_type"] == "agent.joined"

    def test_agent_joined_serialization(self) -> None:
        """AgentJoined to_dict includes capabilities."""
        event = AgentJoined(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            room_name="room-1",
            capabilities=["listen"],
        )
        data = event.to_dict()
        assert data["capabilities"] == ["listen"]
        assert data["room_name"] == "room-1"


class TestAgentLeft:
    """Tests for the AgentLeft event."""

    def test_agent_left_event(self) -> None:
        """AgentLeft event can be created."""
        event = AgentLeft(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            room_name="sprint-room",
        )
        assert event.reason == "normal"

    def test_agent_left_custom_reason(self) -> None:
        """AgentLeft can have a custom reason."""
        event = AgentLeft(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            room_name="test",
            reason="timeout",
        )
        assert event.reason == "timeout"
        assert event.to_dict()["event_type"] == "agent.left"


class TestParticipantJoined:
    """Tests for the ParticipantJoined event."""

    def test_participant_joined_event(self) -> None:
        """ParticipantJoined event can be created."""
        event = ParticipantJoined(
            participant_id=PARTICIPANT_ID,
            meeting_id=MEETING_ID,
            name="Alice",
            role="host",
            connection_type="webrtc",
        )
        assert event.name == "Alice"
        assert event.role == "host"
        assert event.connection_type == "webrtc"

    def test_participant_joined_event_type(self) -> None:
        """ParticipantJoined has correct event_type."""
        event = ParticipantJoined(
            participant_id=PARTICIPANT_ID,
            meeting_id=MEETING_ID,
            name="Bob",
            role="participant",
        )
        assert event.to_dict()["event_type"] == "participant.joined"


class TestParticipantLeft:
    """Tests for the ParticipantLeft event."""

    def test_participant_left_event(self) -> None:
        """ParticipantLeft event can be created."""
        event = ParticipantLeft(
            participant_id=PARTICIPANT_ID,
            meeting_id=MEETING_ID,
        )
        assert event.reason == "normal"
        assert event.to_dict()["event_type"] == "participant.left"

    def test_participant_left_custom_reason(self) -> None:
        """ParticipantLeft can have a custom reason."""
        event = ParticipantLeft(
            participant_id=PARTICIPANT_ID,
            meeting_id=MEETING_ID,
            reason="kicked",
        )
        assert event.reason == "kicked"


class TestAgentData:
    """Tests for the AgentData event."""

    def test_agent_data_event(self) -> None:
        """AgentData event can be created."""
        event = AgentData(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            channel="tasks",
            payload={"action": "extract", "count": 3},
        )
        assert event.channel == "tasks"
        assert event.payload["action"] == "extract"

    def test_agent_data_event_type(self) -> None:
        """AgentData has correct event_type."""
        event = AgentData(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            channel="test",
            payload={},
        )
        assert event.to_dict()["event_type"] == "agent.data"

    def test_agent_data_serialization(self) -> None:
        """AgentData to_dict includes channel and payload."""
        event = AgentData(
            agent_config_id=AGENT_CONFIG_ID,
            meeting_id=MEETING_ID,
            channel="summary",
            payload={"text": "Meeting summary here"},
        )
        data = event.to_dict()
        assert data["channel"] == "summary"
        assert data["payload"]["text"] == "Meeting summary here"
