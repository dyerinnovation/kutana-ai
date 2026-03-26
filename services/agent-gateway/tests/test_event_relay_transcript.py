"""Tests for EventRelay transcript event handling."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agent_gateway.event_relay import EventRelay


@pytest.fixture
def connection_manager():
    """Create a mock ConnectionManager."""
    return MagicMock()


@pytest.fixture
def relay(connection_manager):
    """Create an EventRelay with mocked Redis."""
    with patch("agent_gateway.event_relay.redis") as mock_redis_module:
        mock_redis = AsyncMock()
        mock_redis_module.from_url.return_value = mock_redis
        relay = EventRelay(
            redis_url="redis://localhost:6379/0",
            connection_manager=connection_manager,
        )
        relay._redis = mock_redis
        return relay


def _make_session(capabilities=None):
    """Create a mock session with specified capabilities."""
    session = AsyncMock()
    session.session_id = uuid4()
    session.capabilities = capabilities or ["listen", "transcribe"]
    session.send_transcript = AsyncMock()
    session.send_event = AsyncMock()
    return session


class TestTranscriptEventHandling:
    """Tests for transcript.segment.final routing."""

    async def test_transcript_event_calls_send_transcript(
        self, relay, connection_manager
    ) -> None:
        """transcript.segment.final calls session.send_transcript with correct fields."""
        meeting_id = uuid4()
        session = _make_session(capabilities=["listen", "transcribe"])
        connection_manager.get_meeting_sessions.return_value = [session]

        segment_data = {
            "speaker_id": "speaker-1",
            "text": "Hello world",
            "start_time": 1.5,
            "end_time": 3.2,
            "confidence": 0.95,
        }
        payload = {
            "meeting_id": str(meeting_id),
            "segment": segment_data,
        }

        await relay._handle_event(
            "1-0",
            {
                "event_type": "transcript.segment.final",
                "payload": json.dumps(payload),
            },
        )

        session.send_transcript.assert_awaited_once_with(
            meeting_id=meeting_id,
            speaker_id="speaker-1",
            text="Hello world",
            start_time=1.5,
            end_time=3.2,
            confidence=0.95,
            speaker_name=None,
        )
        session.send_event.assert_not_awaited()

    async def test_transcript_event_defaults(
        self, relay, connection_manager
    ) -> None:
        """Missing segment fields use defaults."""
        meeting_id = uuid4()
        session = _make_session(capabilities=["listen"])
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = {
            "meeting_id": str(meeting_id),
            "segment": {},
        }

        await relay._handle_event(
            "1-0",
            {
                "event_type": "transcript.segment.final",
                "payload": json.dumps(payload),
            },
        )

        session.send_transcript.assert_awaited_once_with(
            meeting_id=meeting_id,
            speaker_id=None,
            text="",
            start_time=0.0,
            end_time=0.0,
            confidence=1.0,
            speaker_name=None,
        )

    async def test_transcript_event_missing_segment_key(
        self, relay, connection_manager
    ) -> None:
        """Payload without 'segment' key uses empty dict defaults."""
        meeting_id = uuid4()
        session = _make_session(capabilities=["transcribe"])
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = {"meeting_id": str(meeting_id)}

        await relay._handle_event(
            "1-0",
            {
                "event_type": "transcript.segment.final",
                "payload": json.dumps(payload),
            },
        )

        session.send_transcript.assert_awaited_once_with(
            meeting_id=meeting_id,
            speaker_id=None,
            text="",
            start_time=0.0,
            end_time=0.0,
            confidence=1.0,
            speaker_name=None,
        )


class TestNonTranscriptEvents:
    """Tests that non-transcript events still use send_event."""

    async def test_meeting_event_calls_send_event(
        self, relay, connection_manager
    ) -> None:
        """meeting.started event calls session.send_event."""
        meeting_id = uuid4()
        session = _make_session(capabilities=["listen"])
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = {"meeting_id": str(meeting_id)}

        await relay._handle_event(
            "1-0",
            {
                "event_type": "meeting.started",
                "payload": json.dumps(payload),
            },
        )

        session.send_event.assert_awaited_once()
        session.send_transcript.assert_not_awaited()

    async def test_task_event_not_relayed_without_capability(
        self, relay, connection_manager
    ) -> None:
        """task.created event is not relayed to agent without extract_tasks."""
        meeting_id = uuid4()
        session = _make_session(capabilities=["listen"])
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = {"meeting_id": str(meeting_id)}

        await relay._handle_event(
            "1-0",
            {
                "event_type": "task.created",
                "payload": json.dumps(payload),
            },
        )

        session.send_event.assert_not_awaited()
        session.send_transcript.assert_not_awaited()

    async def test_transcript_not_relayed_without_capability(
        self, relay, connection_manager
    ) -> None:
        """transcript.segment.final is not relayed to agent without listen/transcribe."""
        meeting_id = uuid4()
        session = _make_session(capabilities=["data_only"])
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = {
            "meeting_id": str(meeting_id),
            "segment": {"text": "hello"},
        }

        await relay._handle_event(
            "1-0",
            {
                "event_type": "transcript.segment.final",
                "payload": json.dumps(payload),
            },
        )

        session.send_transcript.assert_not_awaited()
        session.send_event.assert_not_awaited()
