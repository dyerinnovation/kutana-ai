"""WebSocket protocol message schemas for the agent gateway.

Client -> Server messages:
    JoinMeeting, AudioData, DataMessage, LeaveMeeting,
    RaiseHand, LowerHand, FinishedSpeaking, GetQueue

Server -> Client messages:
    Joined, TranscriptMessage, AudioMessage, EventMessage,
    ParticipantUpdate, ErrorMessage,
    TurnQueueUpdated, TurnSpeakerChanged, TurnYourTurn
"""

from __future__ import annotations

import enum
from typing import Any, Literal
from uuid import UUID  # noqa: TC003 — used at runtime by Pydantic validators

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Capability(enum.StrEnum):
    """Agent capabilities that can be requested and granted."""

    LISTEN = "listen"
    SPEAK = "speak"
    TRANSCRIBE = "transcribe"
    EXTRACT_TASKS = "extract_tasks"
    DATA_ONLY = "data_only"


# ---------------------------------------------------------------------------
# Client -> Server messages
# ---------------------------------------------------------------------------


class JoinMeeting(BaseModel):
    """Request to join a meeting."""

    type: Literal["join_meeting"] = "join_meeting"
    meeting_id: UUID
    capabilities: list[str] = Field(default_factory=lambda: ["listen", "transcribe"])


class AudioData(BaseModel):
    """Audio data from the agent (base64-encoded PCM16 16kHz mono)."""

    type: Literal["audio_data"] = "audio_data"
    data: str
    sequence: int = 0


class DataMessage(BaseModel):
    """Structured data from the agent."""

    type: Literal["data"] = "data"
    channel: str
    payload: dict[str, Any]


class LeaveMeeting(BaseModel):
    """Request to leave the current meeting."""

    type: Literal["leave_meeting"] = "leave_meeting"
    reason: str = "normal"


class RaiseHand(BaseModel):
    """Request to join the speaking queue."""

    type: Literal["raise_hand"] = "raise_hand"
    priority: str = "normal"
    topic: str | None = None


class LowerHand(BaseModel):
    """Request to leave the speaking queue."""

    type: Literal["lower_hand"] = "lower_hand"
    hand_raise_id: str | None = None


class FinishedSpeaking(BaseModel):
    """Signal that the active speaker has finished their turn."""

    type: Literal["finished_speaking"] = "finished_speaking"


class GetQueue(BaseModel):
    """Request the current queue status."""

    type: Literal["get_queue"] = "get_queue"


# ---------------------------------------------------------------------------
# Server -> Client messages
# ---------------------------------------------------------------------------


class Joined(BaseModel):
    """Confirmation that the agent has joined a meeting."""

    type: Literal["joined"] = "joined"
    meeting_id: UUID
    room_name: str | None = None
    participants: list[dict[str, Any]] = Field(default_factory=list)
    granted_capabilities: list[str] = Field(default_factory=list)


class TranscriptMessage(BaseModel):
    """A transcript segment from the meeting."""

    type: Literal["transcript"] = "transcript"
    meeting_id: UUID
    speaker_id: str | None = None
    text: str
    start_time: float
    end_time: float
    confidence: float
    is_final: bool = True


class AudioMessage(BaseModel):
    """Meeting audio forwarded to the agent (base64-encoded PCM16)."""

    type: Literal["audio"] = "audio"
    data: str
    speaker_id: str | None = None


class EventMessage(BaseModel):
    """A domain event from Redis Streams."""

    type: Literal["event"] = "event"
    event_type: str
    payload: dict[str, Any]


class ParticipantUpdate(BaseModel):
    """Notification of participant join/leave."""

    type: Literal["participant_update"] = "participant_update"
    action: str  # "joined" or "left"
    participant_id: UUID
    name: str
    role: str
    connection_type: str | None = None


class ErrorMessage(BaseModel):
    """Error notification sent to the agent."""

    type: Literal["error"] = "error"
    code: str
    message: str
    details: dict[str, Any] | None = None


class TurnQueueUpdated(BaseModel):
    """Broadcast when the speaker queue changes."""

    type: Literal["turn_queue_updated"] = "turn_queue_updated"
    meeting_id: UUID
    active_speaker_id: UUID | None = None
    queue: list[dict[str, Any]] = Field(default_factory=list)


class TurnSpeakerChanged(BaseModel):
    """Broadcast when the active speaker changes."""

    type: Literal["turn_speaker_changed"] = "turn_speaker_changed"
    meeting_id: UUID
    previous_speaker_id: UUID | None = None
    new_speaker_id: UUID | None = None


class TurnYourTurn(BaseModel):
    """Targeted notification sent to the participant who is next to speak."""

    type: Literal["turn_your_turn"] = "turn_your_turn"
    meeting_id: UUID


# ---------------------------------------------------------------------------
# Message type unions for parsing
# ---------------------------------------------------------------------------

CLIENT_MESSAGE_TYPES = {
    "join_meeting": JoinMeeting,
    "audio_data": AudioData,
    "data": DataMessage,
    "leave_meeting": LeaveMeeting,
    "raise_hand": RaiseHand,
    "lower_hand": LowerHand,
    "finished_speaking": FinishedSpeaking,
    "get_queue": GetQueue,
}

SERVER_MESSAGE_TYPES = {
    "joined": Joined,
    "transcript": TranscriptMessage,
    "audio": AudioMessage,
    "event": EventMessage,
    "participant_update": ParticipantUpdate,
    "error": ErrorMessage,
    "turn_queue_updated": TurnQueueUpdated,
    "turn_speaker_changed": TurnSpeakerChanged,
    "turn_your_turn": TurnYourTurn,
}


def parse_client_message(data: dict[str, Any]) -> BaseModel:
    """Parse a raw dict into the appropriate client message type.

    Args:
        data: Raw message dict with a 'type' field.

    Returns:
        Parsed Pydantic model.

    Raises:
        ValueError: If the message type is unknown.
    """
    msg_type = data.get("type")
    if msg_type not in CLIENT_MESSAGE_TYPES:
        msg = f"Unknown client message type: {msg_type}"
        raise ValueError(msg)
    return CLIENT_MESSAGE_TYPES[msg_type].model_validate(data)
