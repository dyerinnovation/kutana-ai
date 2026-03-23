"""Tests for turn management models and events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from convene_core.events.definitions import (
    FinishedSpeaking,
    HandRaised,
    QueueUpdated,
    SpeakerChanged,
    YourTurn,
)
from convene_core.models.turn import (
    HandRaisePriority,
    QueueEntry,
    QueueStatus,
    RaiseHandResult,
    SpeakingStatus,
)

MEETING_ID = uuid4()
PARTICIPANT_A = uuid4()
PARTICIPANT_B = uuid4()
HAND_RAISE_ID = uuid4()


# ---------------------------------------------------------------------------
# HandRaisePriority enum
# ---------------------------------------------------------------------------


class TestHandRaisePriority:
    """Tests for HandRaisePriority enum."""

    def test_normal_value(self) -> None:
        """NORMAL priority has the string value 'normal'."""
        assert HandRaisePriority.NORMAL == "normal"

    def test_urgent_value(self) -> None:
        """URGENT priority has the string value 'urgent'."""
        assert HandRaisePriority.URGENT == "urgent"

    def test_from_string(self) -> None:
        """Can construct from plain string."""
        assert HandRaisePriority("normal") == HandRaisePriority.NORMAL
        assert HandRaisePriority("urgent") == HandRaisePriority.URGENT


# ---------------------------------------------------------------------------
# QueueEntry model
# ---------------------------------------------------------------------------


class TestQueueEntry:
    """Tests for QueueEntry model."""

    def test_defaults_generated(self) -> None:
        """QueueEntry auto-generates hand_raise_id and raised_at."""
        entry = QueueEntry(participant_id=PARTICIPANT_A, position=1)
        assert isinstance(entry.hand_raise_id, UUID)
        assert isinstance(entry.raised_at, datetime)
        assert entry.raised_at.tzinfo is not None
        assert entry.priority == HandRaisePriority.NORMAL
        assert entry.topic is None

    def test_explicit_values(self) -> None:
        """QueueEntry stores all explicit values."""
        entry = QueueEntry(
            participant_id=PARTICIPANT_A,
            hand_raise_id=HAND_RAISE_ID,
            priority=HandRaisePriority.URGENT,
            topic="Budget discussion",
            position=2,
        )
        assert entry.participant_id == PARTICIPANT_A
        assert entry.hand_raise_id == HAND_RAISE_ID
        assert entry.priority == HandRaisePriority.URGENT
        assert entry.topic == "Budget discussion"
        assert entry.position == 2

    def test_position_required(self) -> None:
        """QueueEntry requires a position."""
        with pytest.raises(Exception):
            QueueEntry(participant_id=PARTICIPANT_A)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# QueueStatus model
# ---------------------------------------------------------------------------


class TestQueueStatus:
    """Tests for QueueStatus model."""

    def test_empty_queue(self) -> None:
        """QueueStatus with no speaker and empty queue."""
        status = QueueStatus(meeting_id=MEETING_ID)
        assert status.active_speaker_id is None
        assert status.queue == []

    def test_with_active_speaker(self) -> None:
        """QueueStatus stores active speaker ID."""
        status = QueueStatus(meeting_id=MEETING_ID, active_speaker_id=PARTICIPANT_A)
        assert status.active_speaker_id == PARTICIPANT_A

    def test_with_queue(self) -> None:
        """QueueStatus stores ordered queue entries."""
        entry = QueueEntry(participant_id=PARTICIPANT_B, position=1)
        status = QueueStatus(
            meeting_id=MEETING_ID,
            active_speaker_id=PARTICIPANT_A,
            queue=[entry],
        )
        assert len(status.queue) == 1
        assert status.queue[0].participant_id == PARTICIPANT_B


# ---------------------------------------------------------------------------
# SpeakingStatus model
# ---------------------------------------------------------------------------


class TestSpeakingStatus:
    """Tests for SpeakingStatus model."""

    def test_active_speaker(self) -> None:
        """SpeakingStatus correctly represents the active speaker."""
        status = SpeakingStatus(
            participant_id=PARTICIPANT_A,
            is_speaking=True,
            in_queue=False,
        )
        assert status.is_speaking is True
        assert status.in_queue is False
        assert status.queue_position is None
        assert status.hand_raise_id is None

    def test_in_queue(self) -> None:
        """SpeakingStatus correctly represents a queued participant."""
        hrid = uuid4()
        status = SpeakingStatus(
            participant_id=PARTICIPANT_B,
            is_speaking=False,
            in_queue=True,
            queue_position=2,
            hand_raise_id=hrid,
        )
        assert status.is_speaking is False
        assert status.in_queue is True
        assert status.queue_position == 2
        assert status.hand_raise_id == hrid

    def test_idle(self) -> None:
        """SpeakingStatus for a participant not speaking and not in queue."""
        status = SpeakingStatus(
            participant_id=PARTICIPANT_A,
            is_speaking=False,
            in_queue=False,
        )
        assert status.is_speaking is False
        assert status.in_queue is False
        assert status.queue_position is None


# ---------------------------------------------------------------------------
# RaiseHandResult model
# ---------------------------------------------------------------------------


class TestRaiseHandResult:
    """Tests for RaiseHandResult model."""

    def test_added_to_queue(self) -> None:
        """RaiseHandResult for a normal queue addition."""
        result = RaiseHandResult(
            queue_position=3,
            hand_raise_id=HAND_RAISE_ID,
            was_promoted=False,
        )
        assert result.queue_position == 3
        assert result.hand_raise_id == HAND_RAISE_ID
        assert result.was_promoted is False

    def test_immediately_promoted(self) -> None:
        """RaiseHandResult for immediate promotion as active speaker."""
        result = RaiseHandResult(
            queue_position=0,
            hand_raise_id=HAND_RAISE_ID,
            was_promoted=True,
        )
        assert result.queue_position == 0
        assert result.was_promoted is True


# ---------------------------------------------------------------------------
# Turn management events
# ---------------------------------------------------------------------------


class TestHandRaisedEvent:
    """Tests for HandRaised event."""

    def test_event_type(self) -> None:
        """HandRaised has the correct event_type."""
        event = HandRaised(
            meeting_id=MEETING_ID,
            participant_id=PARTICIPANT_A,
            hand_raise_id=HAND_RAISE_ID,
            queue_position=1,
        )
        assert event.to_dict()["event_type"] == "turn.hand.raised"

    def test_serialization(self) -> None:
        """HandRaised serializes all fields correctly."""
        event = HandRaised(
            meeting_id=MEETING_ID,
            participant_id=PARTICIPANT_A,
            hand_raise_id=HAND_RAISE_ID,
            queue_position=2,
            priority="urgent",
            topic="Quarterly review",
        )
        data = event.to_dict()
        assert data["meeting_id"] == str(MEETING_ID)
        assert data["participant_id"] == str(PARTICIPANT_A)
        assert data["queue_position"] == 2
        assert data["priority"] == "urgent"
        assert data["topic"] == "Quarterly review"

    def test_defaults(self) -> None:
        """HandRaised defaults to normal priority and no topic."""
        event = HandRaised(
            meeting_id=MEETING_ID,
            participant_id=PARTICIPANT_A,
            hand_raise_id=HAND_RAISE_ID,
            queue_position=1,
        )
        assert event.priority == "normal"
        assert event.topic is None


class TestSpeakerChangedEvent:
    """Tests for SpeakerChanged event."""

    def test_event_type(self) -> None:
        """SpeakerChanged has the correct event_type."""
        event = SpeakerChanged(meeting_id=MEETING_ID)
        assert event.to_dict()["event_type"] == "turn.speaker.changed"

    def test_with_transition(self) -> None:
        """SpeakerChanged captures both previous and new speaker."""
        event = SpeakerChanged(
            meeting_id=MEETING_ID,
            previous_speaker_id=PARTICIPANT_A,
            new_speaker_id=PARTICIPANT_B,
        )
        data = event.to_dict()
        assert data["previous_speaker_id"] == str(PARTICIPANT_A)
        assert data["new_speaker_id"] == str(PARTICIPANT_B)

    def test_null_speakers(self) -> None:
        """SpeakerChanged supports None for both fields."""
        event = SpeakerChanged(meeting_id=MEETING_ID)
        assert event.previous_speaker_id is None
        assert event.new_speaker_id is None


class TestQueueUpdatedEvent:
    """Tests for QueueUpdated event."""

    def test_event_type(self) -> None:
        """QueueUpdated has the correct event_type."""
        event = QueueUpdated(meeting_id=MEETING_ID)
        assert event.to_dict()["event_type"] == "turn.queue.updated"

    def test_with_queue(self) -> None:
        """QueueUpdated carries queue entries."""
        entry = {"position": 1, "participant_id": str(PARTICIPANT_B), "priority": "normal"}
        event = QueueUpdated(
            meeting_id=MEETING_ID,
            active_speaker_id=PARTICIPANT_A,
            queue=[entry],
        )
        data = event.to_dict()
        assert data["active_speaker_id"] == str(PARTICIPANT_A)
        assert len(data["queue"]) == 1


class TestFinishedSpeakingEvent:
    """Tests for FinishedSpeaking event."""

    def test_event_type(self) -> None:
        """FinishedSpeaking has the correct event_type."""
        event = FinishedSpeaking(meeting_id=MEETING_ID, participant_id=PARTICIPANT_A)
        assert event.to_dict()["event_type"] == "turn.speaker.finished"

    def test_serialization(self) -> None:
        """FinishedSpeaking serializes correctly."""
        event = FinishedSpeaking(meeting_id=MEETING_ID, participant_id=PARTICIPANT_A)
        data = event.to_dict()
        assert data["participant_id"] == str(PARTICIPANT_A)
        assert data["meeting_id"] == str(MEETING_ID)


class TestYourTurnEvent:
    """Tests for YourTurn event."""

    def test_event_type(self) -> None:
        """YourTurn has the correct event_type."""
        event = YourTurn(meeting_id=MEETING_ID, participant_id=PARTICIPANT_A)
        assert event.to_dict()["event_type"] == "turn.your_turn"

    def test_serialization(self) -> None:
        """YourTurn serializes correctly."""
        event = YourTurn(meeting_id=MEETING_ID, participant_id=PARTICIPANT_A)
        data = event.to_dict()
        assert data["participant_id"] == str(PARTICIPANT_A)
