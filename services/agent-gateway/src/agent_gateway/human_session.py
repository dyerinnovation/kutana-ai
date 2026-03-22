"""Per-human-browser session lifecycle management.

Humans differ from agents in three ways:
1. They auto-join the meeting on connect — no JoinMeeting message needed.
2. They always get speak + listen + transcribe capabilities.
3. There is no per-user agent_config_id — the user's own ID from the JWT sub
   serves as the identifier.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from agent_gateway.protocol import (
    AudioData,
    ErrorMessage,
    EventMessage,
    Joined,
    ParticipantUpdate,
    TranscriptMessage,
)

if TYPE_CHECKING:
    from fastapi import WebSocket

    from agent_gateway.audio_bridge import AudioBridge
    from agent_gateway.auth import AgentIdentity
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Human participants always receive these capabilities — no negotiation needed.
HUMAN_CAPABILITIES: list[str] = ["listen", "speak", "transcribe"]


class HumanSessionHandler:
    """Manages the lifecycle of a human browser WebSocket connection.

    Unlike AgentSessionHandler, the meeting is joined automatically on
    connect (meeting_id comes from the URL query param). No JoinMeeting
    message is required from the client.

    Attributes:
        session_id: Unique identifier for this session.
        agent_name: Display name (kept as agent_name for ConnectionManager compat).
        meeting_id: The meeting this session is connected to.
        capabilities: Always speak + listen + transcribe for humans.
    """

    def __init__(
        self,
        websocket: WebSocket,
        identity: AgentIdentity,
        meeting_id: UUID,
        connection_manager: ConnectionManager,
        audio_bridge: AudioBridge | None = None,
    ) -> None:
        """Initialise the human session handler.

        Args:
            websocket: The WebSocket connection.
            identity: Validated identity from JWT (sub = user ID, not agent_config_id).
            meeting_id: The meeting to auto-join.
            connection_manager: The global connection manager.
            audio_bridge: Optional AudioBridge for STT processing.
        """
        self._ws = websocket
        self._identity = identity
        self._manager = connection_manager
        self._audio_bridge = audio_bridge
        self.session_id: UUID = uuid4()
        self.agent_name: str = identity.name  # field name kept for ConnectionManager compat
        self.meeting_id: UUID = meeting_id
        self.capabilities: list[str] = list(HUMAN_CAPABILITIES)
        self._connected_at: datetime = datetime.now(tz=UTC)

    async def handle(self) -> None:
        """Auto-join the meeting and enter the message loop.

        Unlike agents, humans do not send a join_meeting message. The meeting
        join is triggered immediately when the WebSocket opens.
        """
        # Auto-join: register in meeting, start audio pipeline
        self._manager.join_meeting(self.session_id, self.meeting_id)

        if self._audio_bridge is not None:
            await self._audio_bridge.ensure_pipeline(self.meeting_id)

        # Send joined confirmation so the frontend can transition to "connected"
        response = Joined(
            meeting_id=self.meeting_id,
            granted_capabilities=self.capabilities,
        )
        await self._send(response.model_dump(mode="json"))
        logger.info(
            "Human %s joined meeting %s",
            self.agent_name,
            self.meeting_id,
        )

        try:
            while True:
                raw = await self._ws.receive_text()
                data = json.loads(raw)
                await self._dispatch(data)
        except Exception as e:
            logger.info(
                "Human session %s disconnected: %s",
                self.session_id,
                type(e).__name__,
            )
        finally:
            await self._cleanup()

    async def _dispatch(self, data: dict[str, Any]) -> None:
        """Route an incoming message to the appropriate handler.

        Humans can send: audio_data, leave_meeting.
        All other message types are silently ignored.

        Args:
            data: Raw parsed message dict.
        """
        msg_type = data.get("type")

        if msg_type == "audio_data":
            try:
                await self._handle_audio(AudioData.model_validate(data))
            except Exception:
                await self._send_error("invalid_message", "Invalid audio_data message")
        elif msg_type == "leave_meeting":
            await self._handle_leave()

    async def _handle_audio(self, msg: AudioData) -> None:
        """Forward PCM16 audio from the browser to the STT pipeline.

        Args:
            msg: The audio data message with base64-encoded PCM16.
        """
        try:
            audio_bytes = base64.b64decode(msg.data)
        except Exception:
            await self._send_error("invalid_audio", "Invalid base64 audio data")
            return

        if self._audio_bridge is not None:
            await self._audio_bridge.process_audio(self.meeting_id, audio_bytes)

        logger.debug(
            "Received %d bytes of audio from human %s",
            len(audio_bytes),
            self.agent_name,
        )

    async def _handle_leave(self) -> None:
        """Handle a voluntary leave from the browser."""
        self._manager.leave_meeting(self.session_id, self.meeting_id)
        logger.info("Human %s left meeting %s", self.agent_name, self.meeting_id)

    # ------------------------------------------------------------------
    # Outbound delivery — called by EventRelay (same interface as AgentSessionHandler)
    # ------------------------------------------------------------------

    async def send_transcript(
        self,
        meeting_id: UUID,
        speaker_id: str | None,
        text: str,
        start_time: float,
        end_time: float,
        confidence: float,
    ) -> None:
        """Send a transcript segment to the browser.

        Args:
            meeting_id: The meeting the transcript belongs to.
            speaker_id: Speaker identifier.
            text: Transcribed text.
            start_time: Segment start time.
            end_time: Segment end time.
            confidence: STT confidence score.
        """
        msg = TranscriptMessage(
            meeting_id=meeting_id,
            speaker_id=speaker_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            confidence=confidence,
        )
        await self._send(msg.model_dump(mode="json"))

    async def send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Send a domain event to the browser.

        Args:
            event_type: The event type string.
            payload: Event data.
        """
        msg = EventMessage(event_type=event_type, payload=payload)
        await self._send(msg.model_dump(mode="json"))

    async def send_participant_update(
        self,
        action: str,
        participant_id: UUID,
        name: str,
        role: str,
        connection_type: str | None = None,
    ) -> None:
        """Send a participant join/leave notification to the browser.

        Args:
            action: "joined" or "left".
            participant_id: The participant's ID.
            name: Display name.
            role: Participant role.
            connection_type: How they're connected.
        """
        msg = ParticipantUpdate(
            action=action,
            participant_id=participant_id,
            name=name,
            role=role,
            connection_type=connection_type,
        )
        await self._send(msg.model_dump(mode="json"))

    async def _send(self, data: dict[str, Any]) -> None:
        """Send a JSON message to the browser.

        Args:
            data: Message dict to serialize and send.
        """
        try:
            await self._ws.send_json(data)
        except Exception:
            logger.warning(
                "Failed to send message to human %s",
                self.agent_name,
            )

    async def _send_error(self, code: str, message: str) -> None:
        """Send an error message to the browser.

        Args:
            code: Error code string.
            message: Human-readable error message.
        """
        err = ErrorMessage(code=code, message=message)
        await self._send(err.model_dump(mode="json"))

    async def _cleanup(self) -> None:
        """Clean up session state on disconnect."""
        self._manager.leave_meeting(self.session_id, self.meeting_id)
        self._manager.unregister(self.session_id)
