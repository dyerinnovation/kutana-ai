"""Tests for Convene AI domain models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from convene_core.models.agent import AgentConfig
from convene_core.models.agent_session import (
    AgentSession,
    AgentSessionStatus,
    ConnectionType,
)
from convene_core.models.decision import Decision
from convene_core.models.meeting import Meeting, MeetingStatus
from convene_core.models.participant import Participant, ParticipantRole
from convene_core.models.room import Room, RoomStatus
from convene_core.models.task import (
    VALID_TRANSITIONS,
    Task,
    TaskPriority,
    TaskStatus,
)
from convene_core.models.transcript import TranscriptSegment

# ---- Helpers ----


def _utc(year: int, month: int, day: int, hour: int = 0) -> datetime:
    """Create a timezone-aware UTC datetime."""
    return datetime(year, month, day, hour, tzinfo=UTC)


MEETING_ID = uuid4()
PARTICIPANT_ID = uuid4()


# ---- Meeting Tests ----


class TestMeeting:
    """Tests for the Meeting model."""

    def test_create_meeting_with_defaults(self) -> None:
        """Meeting can be created with required fields only."""
        meeting = Meeting(
            platform="zoom",
            dial_in_number="+15551234567",
            meeting_code="123456",
            scheduled_at=_utc(2026, 3, 1, 10),
        )
        assert isinstance(meeting.id, UUID)
        assert meeting.status == MeetingStatus.SCHEDULED
        assert meeting.participants == []
        assert meeting.title is None
        assert meeting.started_at is None
        assert meeting.ended_at is None
        assert meeting.created_at.tzinfo is not None
        assert meeting.updated_at.tzinfo is not None

    def test_create_meeting_with_all_fields(self) -> None:
        """Meeting can be created with all fields populated."""
        started = _utc(2026, 3, 1, 10)
        ended = _utc(2026, 3, 1, 11)
        meeting = Meeting(
            platform="teams",
            dial_in_number="+15559876543",
            meeting_code="ABCDEF",
            title="Sprint Planning",
            scheduled_at=_utc(2026, 3, 1, 10),
            started_at=started,
            ended_at=ended,
            status=MeetingStatus.COMPLETED,
            participants=[uuid4(), uuid4()],
        )
        assert meeting.title == "Sprint Planning"
        assert meeting.status == MeetingStatus.COMPLETED
        assert len(meeting.participants) == 2

    def test_meeting_status_enum_values(self) -> None:
        """MeetingStatus enum has all expected values."""
        assert MeetingStatus.SCHEDULED == "scheduled"
        assert MeetingStatus.ACTIVE == "active"
        assert MeetingStatus.COMPLETED == "completed"
        assert MeetingStatus.FAILED == "failed"

    def test_meeting_started_after_ended_raises(self) -> None:
        """Validation error if started_at > ended_at."""
        with pytest.raises(ValidationError, match="started_at must be <= ended_at"):
            Meeting(
                platform="zoom",
                dial_in_number="+15551234567",
                meeting_code="123456",
                scheduled_at=_utc(2026, 3, 1, 10),
                started_at=_utc(2026, 3, 1, 12),
                ended_at=_utc(2026, 3, 1, 11),
            )

    def test_meeting_naive_datetime_raises(self) -> None:
        """Validation error if scheduled_at is not timezone-aware."""
        with pytest.raises(ValidationError, match="must be timezone-aware"):
            Meeting(
                platform="zoom",
                dial_in_number="+15551234567",
                meeting_code="123456",
                scheduled_at=datetime(2026, 3, 1, 10),
            )

    def test_meeting_serialization_roundtrip(self) -> None:
        """Meeting can be serialized and deserialized."""
        meeting = Meeting(
            platform="meet",
            dial_in_number="+15551234567",
            meeting_code="789012",
            scheduled_at=_utc(2026, 3, 1, 10),
        )
        data = meeting.model_dump(mode="json")
        restored = Meeting.model_validate(data)
        assert restored.id == meeting.id
        assert restored.platform == meeting.platform


# ---- Participant Tests ----


class TestParticipant:
    """Tests for the Participant model."""

    def test_create_participant_with_defaults(self) -> None:
        """Participant can be created with minimal fields."""
        participant = Participant(name="Alice")
        assert isinstance(participant.id, UUID)
        assert participant.role == ParticipantRole.PARTICIPANT
        assert participant.email is None
        assert participant.speaker_id is None

    def test_create_participant_with_all_fields(self) -> None:
        """Participant can be created with all fields."""
        participant = Participant(
            name="Bob",
            email="bob@example.com",
            speaker_id="spk_001",
            role=ParticipantRole.HOST,
        )
        assert participant.email == "bob@example.com"
        assert participant.role == ParticipantRole.HOST

    def test_participant_role_enum(self) -> None:
        """ParticipantRole has all expected values."""
        assert ParticipantRole.HOST == "host"
        assert ParticipantRole.PARTICIPANT == "participant"
        assert ParticipantRole.AGENT == "agent"

    def test_participant_serialization_roundtrip(self) -> None:
        """Participant can be serialized and deserialized."""
        p = Participant(name="Charlie", role=ParticipantRole.AGENT)
        data = p.model_dump(mode="json")
        restored = Participant.model_validate(data)
        assert restored.id == p.id
        assert restored.role == ParticipantRole.AGENT


# ---- Task Tests ----


class TestTask:
    """Tests for the Task model."""

    def test_create_task_with_defaults(self) -> None:
        """Task can be created with required fields only."""
        task = Task(meeting_id=MEETING_ID, description="Write report")
        assert isinstance(task.id, UUID)
        assert task.priority == TaskPriority.MEDIUM
        assert task.status == TaskStatus.PENDING
        assert task.dependencies == []
        assert task.assignee_id is None
        assert task.due_date is None
        assert task.source_utterance is None

    def test_create_task_with_all_fields(self) -> None:
        """Task can be created with all fields populated."""
        dep_id = uuid4()
        task = Task(
            meeting_id=MEETING_ID,
            description="Review PR",
            assignee_id=PARTICIPANT_ID,
            due_date=date(2026, 3, 15),
            priority=TaskPriority.HIGH,
            status=TaskStatus.IN_PROGRESS,
            dependencies=[dep_id],
            source_utterance="Bob said he would review the PR.",
        )
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.IN_PROGRESS
        assert len(task.dependencies) == 1

    def test_task_priority_enum(self) -> None:
        """TaskPriority has all expected values."""
        assert TaskPriority.LOW == "low"
        assert TaskPriority.MEDIUM == "medium"
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.CRITICAL == "critical"

    def test_task_status_enum(self) -> None:
        """TaskStatus has all expected values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.BLOCKED == "blocked"

    def test_valid_transitions(self) -> None:
        """Valid task status transitions are allowed."""
        assert Task.validate_transition(TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        assert Task.validate_transition(TaskStatus.PENDING, TaskStatus.BLOCKED)
        assert Task.validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE)
        assert Task.validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)
        assert Task.validate_transition(TaskStatus.BLOCKED, TaskStatus.PENDING)
        assert Task.validate_transition(TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS)

    def test_invalid_transitions(self) -> None:
        """Invalid task status transitions are rejected."""
        assert not Task.validate_transition(TaskStatus.PENDING, TaskStatus.DONE)
        assert not Task.validate_transition(TaskStatus.DONE, TaskStatus.PENDING)
        assert not Task.validate_transition(TaskStatus.DONE, TaskStatus.IN_PROGRESS)
        assert not Task.validate_transition(TaskStatus.DONE, TaskStatus.BLOCKED)
        assert not Task.validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.PENDING)

    def test_done_is_terminal(self) -> None:
        """DONE status has no valid outgoing transitions."""
        assert VALID_TRANSITIONS[TaskStatus.DONE] == set()

    def test_task_serialization_roundtrip(self) -> None:
        """Task can be serialized and deserialized."""
        task = Task(
            meeting_id=MEETING_ID,
            description="Deploy to staging",
            priority=TaskPriority.CRITICAL,
        )
        data = task.model_dump(mode="json")
        restored = Task.model_validate(data)
        assert restored.id == task.id
        assert restored.priority == TaskPriority.CRITICAL


# ---- Decision Tests ----


class TestDecision:
    """Tests for the Decision model."""

    def test_create_decision(self) -> None:
        """Decision can be created with required fields."""
        decision = Decision(
            meeting_id=MEETING_ID,
            description="Use Python for the backend",
            decided_by_id=PARTICIPANT_ID,
        )
        assert isinstance(decision.id, UUID)
        assert decision.participants_present == []

    def test_create_decision_with_participants(self) -> None:
        """Decision tracks which participants were present."""
        p1, p2 = uuid4(), uuid4()
        decision = Decision(
            meeting_id=MEETING_ID,
            description="Approve budget",
            decided_by_id=PARTICIPANT_ID,
            participants_present=[p1, p2],
        )
        assert len(decision.participants_present) == 2

    def test_decision_serialization_roundtrip(self) -> None:
        """Decision can be serialized and deserialized."""
        decision = Decision(
            meeting_id=MEETING_ID,
            description="Ship v1",
            decided_by_id=PARTICIPANT_ID,
        )
        data = decision.model_dump(mode="json")
        restored = Decision.model_validate(data)
        assert restored.id == decision.id


# ---- TranscriptSegment Tests ----


class TestTranscriptSegment:
    """Tests for the TranscriptSegment model."""

    def test_create_segment_with_defaults(self) -> None:
        """TranscriptSegment can be created with required fields."""
        segment = TranscriptSegment(
            meeting_id=MEETING_ID,
            text="Hello everyone",
            start_time=0.0,
            end_time=2.5,
        )
        assert isinstance(segment.id, UUID)
        assert segment.confidence == 1.0
        assert segment.speaker_id is None

    def test_create_segment_with_all_fields(self) -> None:
        """TranscriptSegment with all fields populated."""
        segment = TranscriptSegment(
            meeting_id=MEETING_ID,
            speaker_id="spk_001",
            text="Let's get started",
            start_time=5.0,
            end_time=7.5,
            confidence=0.95,
        )
        assert segment.speaker_id == "spk_001"
        assert segment.confidence == 0.95

    def test_confidence_too_low_raises(self) -> None:
        """Validation error if confidence < 0.0."""
        with pytest.raises(ValidationError, match="confidence must be between"):
            TranscriptSegment(
                meeting_id=MEETING_ID,
                text="test",
                start_time=0.0,
                end_time=1.0,
                confidence=-0.1,
            )

    def test_confidence_too_high_raises(self) -> None:
        """Validation error if confidence > 1.0."""
        with pytest.raises(ValidationError, match="confidence must be between"):
            TranscriptSegment(
                meeting_id=MEETING_ID,
                text="test",
                start_time=0.0,
                end_time=1.0,
                confidence=1.5,
            )

    def test_confidence_boundary_values(self) -> None:
        """Confidence at exact boundaries (0.0 and 1.0) is valid."""
        seg_zero = TranscriptSegment(
            meeting_id=MEETING_ID,
            text="test",
            start_time=0.0,
            end_time=1.0,
            confidence=0.0,
        )
        assert seg_zero.confidence == 0.0

        seg_one = TranscriptSegment(
            meeting_id=MEETING_ID,
            text="test",
            start_time=0.0,
            end_time=1.0,
            confidence=1.0,
        )
        assert seg_one.confidence == 1.0

    def test_start_time_equal_end_time_raises(self) -> None:
        """Validation error if start_time == end_time."""
        with pytest.raises(ValidationError, match="start_time must be less than end_time"):
            TranscriptSegment(
                meeting_id=MEETING_ID,
                text="test",
                start_time=5.0,
                end_time=5.0,
            )

    def test_start_time_after_end_time_raises(self) -> None:
        """Validation error if start_time > end_time."""
        with pytest.raises(ValidationError, match="start_time must be less than end_time"):
            TranscriptSegment(
                meeting_id=MEETING_ID,
                text="test",
                start_time=10.0,
                end_time=5.0,
            )

    def test_segment_serialization_roundtrip(self) -> None:
        """TranscriptSegment can be serialized and deserialized."""
        segment = TranscriptSegment(
            meeting_id=MEETING_ID,
            text="Testing roundtrip",
            start_time=0.0,
            end_time=3.0,
            confidence=0.88,
        )
        data = segment.model_dump(mode="json")
        restored = TranscriptSegment.model_validate(data)
        assert restored.id == segment.id
        assert restored.confidence == segment.confidence


# ---- AgentConfig Tests ----


class TestAgentConfig:
    """Tests for the AgentConfig model."""

    def test_create_agent_config_with_defaults(self) -> None:
        """AgentConfig can be created with required fields only."""
        config = AgentConfig(
            name="Meeting Assistant",
            system_prompt="You are a helpful meeting assistant.",
        )
        assert isinstance(config.id, UUID)
        assert config.voice_id is None
        assert config.capabilities == []
        assert config.meeting_type_filter == []

    def test_create_agent_config_with_all_fields(self) -> None:
        """AgentConfig can be created with all fields populated."""
        config = AgentConfig(
            name="Sprint Bot",
            voice_id="voice_abc123",
            system_prompt="You facilitate sprint meetings.",
            capabilities=["task_extraction", "summarization"],
            meeting_type_filter=["standup", "sprint_planning"],
        )
        assert config.voice_id == "voice_abc123"
        assert len(config.capabilities) == 2
        assert "standup" in config.meeting_type_filter

    def test_agent_config_serialization_roundtrip(self) -> None:
        """AgentConfig can be serialized and deserialized."""
        config = AgentConfig(
            name="Test Agent",
            system_prompt="Testing.",
        )
        data = config.model_dump(mode="json")
        restored = AgentConfig.model_validate(data)
        assert restored.id == config.id
        assert restored.name == config.name

    def test_agent_config_new_fields(self) -> None:
        """AgentConfig has new agent-gateway fields with defaults."""
        config = AgentConfig(
            name="Gateway Agent",
            system_prompt="Test.",
        )
        assert config.agent_type == "custom"
        assert config.protocol_version == "1.0"
        assert config.default_capabilities == []
        assert config.max_concurrent_sessions == 1

    def test_agent_config_custom_new_fields(self) -> None:
        """AgentConfig new fields can be customized."""
        config = AgentConfig(
            name="LiveKit Agent",
            system_prompt="Test.",
            agent_type="livekit",
            protocol_version="2.0",
            default_capabilities=["listen", "speak"],
            max_concurrent_sessions=5,
        )
        assert config.agent_type == "livekit"
        assert config.protocol_version == "2.0"
        assert config.default_capabilities == ["listen", "speak"]
        assert config.max_concurrent_sessions == 5


# ---- Room Tests ----


class TestRoom:
    """Tests for the Room model."""

    def test_create_room_with_defaults(self) -> None:
        """Room can be created with just a name."""
        room = Room(name="sprint-planning-2026-03-01")
        assert isinstance(room.id, UUID)
        assert room.name == "sprint-planning-2026-03-01"
        assert room.status == RoomStatus.PENDING
        assert room.meeting_id is None
        assert room.livekit_room_id is None
        assert room.max_participants == 0

    def test_create_room_with_all_fields(self) -> None:
        """Room can be created with all fields populated."""
        meeting_id = uuid4()
        room = Room(
            name="standup-daily",
            meeting_id=meeting_id,
            livekit_room_id="lk_room_abc123",
            status=RoomStatus.ACTIVE,
            max_participants=10,
        )
        assert room.meeting_id == meeting_id
        assert room.livekit_room_id == "lk_room_abc123"
        assert room.status == RoomStatus.ACTIVE
        assert room.max_participants == 10

    def test_room_status_enum_values(self) -> None:
        """RoomStatus enum has all expected values."""
        assert RoomStatus.PENDING == "pending"
        assert RoomStatus.ACTIVE == "active"
        assert RoomStatus.CLOSED == "closed"

    def test_room_serialization_roundtrip(self) -> None:
        """Room can be serialized and deserialized."""
        room = Room(name="test-room")
        data = room.model_dump(mode="json")
        restored = Room.model_validate(data)
        assert restored.id == room.id
        assert restored.name == room.name


# ---- AgentSession Tests ----


class TestAgentSession:
    """Tests for the AgentSession model."""

    def test_create_session_with_defaults(self) -> None:
        """AgentSession can be created with required fields."""
        agent_id = uuid4()
        meeting_id = uuid4()
        session = AgentSession(
            agent_config_id=agent_id,
            meeting_id=meeting_id,
        )
        assert isinstance(session.id, UUID)
        assert session.agent_config_id == agent_id
        assert session.meeting_id == meeting_id
        assert session.connection_type == ConnectionType.AGENT_GATEWAY
        assert session.status == AgentSessionStatus.CONNECTING
        assert session.capabilities == []
        assert session.connected_at is None
        assert session.disconnected_at is None

    def test_create_session_with_all_fields(self) -> None:
        """AgentSession with all fields populated."""
        now = _utc(2026, 3, 1, 10)
        session = AgentSession(
            agent_config_id=uuid4(),
            meeting_id=uuid4(),
            room_name="sprint-room",
            connection_type=ConnectionType.WEBRTC,
            capabilities=["listen", "speak", "transcribe"],
            status=AgentSessionStatus.ACTIVE,
            connected_at=now,
        )
        assert session.room_name == "sprint-room"
        assert session.connection_type == ConnectionType.WEBRTC
        assert session.status == AgentSessionStatus.ACTIVE
        assert len(session.capabilities) == 3

    def test_connection_type_enum_values(self) -> None:
        """ConnectionType enum has all expected values."""
        assert ConnectionType.WEBRTC == "webrtc"
        assert ConnectionType.AGENT_GATEWAY == "agent_gateway"
        assert ConnectionType.PHONE == "phone"

    def test_session_status_enum_values(self) -> None:
        """AgentSessionStatus enum has all expected values."""
        assert AgentSessionStatus.CONNECTING == "connecting"
        assert AgentSessionStatus.ACTIVE == "active"
        assert AgentSessionStatus.DISCONNECTED == "disconnected"

    def test_session_serialization_roundtrip(self) -> None:
        """AgentSession can be serialized and deserialized."""
        session = AgentSession(
            agent_config_id=uuid4(),
            meeting_id=uuid4(),
            capabilities=["listen"],
        )
        data = session.model_dump(mode="json")
        restored = AgentSession.model_validate(data)
        assert restored.id == session.id
        assert restored.capabilities == ["listen"]


# ---- Meeting Model Changes Tests ----


class TestMeetingNewFields:
    """Tests for Meeting model changes (optional dial-in, new fields)."""

    def test_meeting_without_dial_in(self) -> None:
        """Meeting can be created without dial_in_number and meeting_code."""
        meeting = Meeting(
            platform="convene",
            scheduled_at=_utc(2026, 3, 1, 10),
        )
        assert meeting.dial_in_number is None
        assert meeting.meeting_code is None
        assert meeting.room_id is None
        assert meeting.room_name is None
        assert meeting.meeting_type == "standard"

    def test_meeting_with_room_fields(self) -> None:
        """Meeting with room-based fields."""
        room_id = uuid4()
        meeting = Meeting(
            platform="convene",
            scheduled_at=_utc(2026, 3, 1, 10),
            room_id=room_id,
            room_name="daily-standup",
            meeting_type="agent_only",
        )
        assert meeting.room_id == room_id
        assert meeting.room_name == "daily-standup"
        assert meeting.meeting_type == "agent_only"


# ---- Participant Model Changes Tests ----


class TestParticipantNewFields:
    """Tests for Participant model changes."""

    def test_observer_role(self) -> None:
        """Participant can have OBSERVER role."""
        p = Participant(name="Observer Bot", role=ParticipantRole.OBSERVER)
        assert p.role == ParticipantRole.OBSERVER
        assert p.role == "observer"

    def test_participant_connection_type(self) -> None:
        """Participant can have a connection_type."""
        p = Participant(
            name="WebRTC User",
            connection_type="webrtc",
        )
        assert p.connection_type == "webrtc"

    def test_participant_agent_config_id(self) -> None:
        """Participant can be linked to an agent config."""
        agent_id = uuid4()
        p = Participant(
            name="Task Bot",
            role=ParticipantRole.AGENT,
            agent_config_id=agent_id,
        )
        assert p.agent_config_id == agent_id
