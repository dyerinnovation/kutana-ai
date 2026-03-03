"""Tests for agent gateway protocol message schemas."""

from __future__ import annotations

from uuid import uuid4

import pytest
from agent_gateway.protocol import (
    AudioData,
    DataMessage,
    ErrorMessage,
    EventMessage,
    Joined,
    JoinMeeting,
    LeaveMeeting,
    ParticipantUpdate,
    TranscriptMessage,
    parse_client_message,
)


class TestClientMessages:
    """Tests for client -> server message schemas."""

    def test_join_meeting_defaults(self) -> None:
        """JoinMeeting has correct defaults."""
        msg = JoinMeeting(meeting_id=uuid4())
        assert msg.type == "join_meeting"
        assert msg.capabilities == ["listen", "transcribe"]

    def test_join_meeting_custom_capabilities(self) -> None:
        """JoinMeeting accepts custom capabilities."""
        msg = JoinMeeting(
            meeting_id=uuid4(),
            capabilities=["listen", "speak", "extract_tasks"],
        )
        assert len(msg.capabilities) == 3

    def test_audio_data(self) -> None:
        """AudioData holds base64 audio."""
        msg = AudioData(data="dGVzdA==", sequence=42)
        assert msg.type == "audio_data"
        assert msg.data == "dGVzdA=="
        assert msg.sequence == 42

    def test_data_message(self) -> None:
        """DataMessage holds channel and payload."""
        msg = DataMessage(
            channel="tasks",
            payload={"action": "extract"},
        )
        assert msg.type == "data"
        assert msg.channel == "tasks"

    def test_leave_meeting_defaults(self) -> None:
        """LeaveMeeting has default reason."""
        msg = LeaveMeeting()
        assert msg.type == "leave_meeting"
        assert msg.reason == "normal"

    def test_leave_meeting_custom_reason(self) -> None:
        """LeaveMeeting accepts custom reason."""
        msg = LeaveMeeting(reason="timeout")
        assert msg.reason == "timeout"


class TestServerMessages:
    """Tests for server -> client message schemas."""

    def test_joined_defaults(self) -> None:
        """Joined has correct defaults."""
        msg = Joined(meeting_id=uuid4())
        assert msg.type == "joined"
        assert msg.participants == []
        assert msg.granted_capabilities == []

    def test_transcript_message(self) -> None:
        """TranscriptMessage holds transcript data."""
        mid = uuid4()
        msg = TranscriptMessage(
            meeting_id=mid,
            speaker_id="spk_001",
            text="Hello world",
            start_time=0.0,
            end_time=2.5,
            confidence=0.95,
        )
        assert msg.type == "transcript"
        assert msg.text == "Hello world"
        assert msg.is_final is True

    def test_event_message(self) -> None:
        """EventMessage wraps a domain event."""
        msg = EventMessage(
            event_type="task.created",
            payload={"task_id": "abc"},
        )
        assert msg.type == "event"
        assert msg.event_type == "task.created"

    def test_participant_update(self) -> None:
        """ParticipantUpdate holds join/leave info."""
        msg = ParticipantUpdate(
            action="joined",
            participant_id=uuid4(),
            name="Alice",
            role="host",
            connection_type="webrtc",
        )
        assert msg.type == "participant_update"
        assert msg.action == "joined"

    def test_error_message(self) -> None:
        """ErrorMessage holds error info."""
        msg = ErrorMessage(
            code="auth_failed",
            message="Invalid token",
        )
        assert msg.type == "error"
        assert msg.details is None


class TestParseClientMessage:
    """Tests for the parse_client_message function."""

    def test_parse_join_meeting(self) -> None:
        """Parses join_meeting message correctly."""
        mid = uuid4()
        msg = parse_client_message({
            "type": "join_meeting",
            "meeting_id": str(mid),
        })
        assert isinstance(msg, JoinMeeting)
        assert msg.meeting_id == mid

    def test_parse_audio_data(self) -> None:
        """Parses audio_data message correctly."""
        msg = parse_client_message({
            "type": "audio_data",
            "data": "dGVzdA==",
            "sequence": 1,
        })
        assert isinstance(msg, AudioData)

    def test_parse_data_message(self) -> None:
        """Parses data message correctly."""
        msg = parse_client_message({
            "type": "data",
            "channel": "tasks",
            "payload": {"key": "value"},
        })
        assert isinstance(msg, DataMessage)

    def test_parse_leave_meeting(self) -> None:
        """Parses leave_meeting message correctly."""
        msg = parse_client_message({"type": "leave_meeting"})
        assert isinstance(msg, LeaveMeeting)

    def test_parse_unknown_type_raises(self) -> None:
        """Unknown message type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown client message type"):
            parse_client_message({"type": "bogus"})

    def test_parse_missing_type_raises(self) -> None:
        """Missing type field raises ValueError."""
        with pytest.raises(ValueError, match="Unknown client message type"):
            parse_client_message({"data": "test"})


class TestMessageSerialization:
    """Tests for message serialization roundtrips."""

    def test_joined_roundtrip(self) -> None:
        """Joined serializes and deserializes."""
        mid = uuid4()
        msg = Joined(
            meeting_id=mid,
            room_name="test-room",
            granted_capabilities=["listen"],
        )
        data = msg.model_dump(mode="json")
        restored = Joined.model_validate(data)
        assert restored.meeting_id == mid
        assert restored.room_name == "test-room"

    def test_transcript_roundtrip(self) -> None:
        """TranscriptMessage serializes and deserializes."""
        mid = uuid4()
        msg = TranscriptMessage(
            meeting_id=mid,
            text="Test transcript",
            start_time=1.0,
            end_time=3.0,
            confidence=0.9,
        )
        data = msg.model_dump(mode="json")
        restored = TranscriptMessage.model_validate(data)
        assert restored.text == "Test transcript"
