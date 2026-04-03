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
    FinishedSpeaking,
    GetQueue,
    Joined,
    LowerHand,
    ParticipantUpdate,
    RaiseHand,
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
        self.source: str = "human"
        self.meeting_id: UUID = meeting_id
        self.capabilities: list[str] = list(HUMAN_CAPABILITIES)
        self.subscribed_channels: set[str] = {"*"}  # humans receive all channel events
        self._connected_at: datetime = datetime.now(tz=UTC)
        self._left_announced: bool = False

    async def handle(self) -> None:
        """Auto-join the meeting and enter the message loop.

        Unlike agents, humans do not send a join_meeting message. The meeting
        join is triggered immediately when the WebSocket opens.
        """
        # Auto-join: register in meeting, start audio pipeline
        self._manager.join_meeting(self.session_id, self.meeting_id)

        if self._audio_bridge is not None:
            await self._audio_bridge.ensure_pipeline(
                self.meeting_id, speaker_name=self.agent_name
            )

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

        # Send existing participants so the browser knows who's already here
        existing_sessions = self._manager.get_meeting_sessions(self.meeting_id)
        for session in existing_sessions:
            if session.session_id == self.session_id:
                continue
            role = "human" if getattr(session, "source", "") == "human" else "agent"
            participant_id = (
                getattr(session, "_identity", None)
                and getattr(session._identity, "agent_config_id", session.session_id)
                or session.session_id
            )
            try:
                await self.send_participant_update(
                    action="joined",
                    participant_id=participant_id,
                    name=session.agent_name,
                    role=role,
                    source=getattr(session, "source", None),
                )
            except Exception:
                logger.warning(
                    "Failed to send existing participant %s to new human session",
                    session.agent_name,
                )

        # Notify others and publish event after sending Joined to self
        await self._broadcast_participant_update("joined")
        await self._publish_participant_event("joined")

        try:
            while True:
                raw = await self._ws.receive_text()
                data = json.loads(raw)
                await self._dispatch(data)
        except Exception as e:
            from fastapi import WebSocketDisconnect
            from starlette.websockets import WebSocketState
            if isinstance(e, WebSocketDisconnect):
                logger.warning(
                    "Human session %s disconnected (code=%s)",
                    self.session_id,
                    e.code,
                )
            else:
                logger.exception(
                    "Human session %s crashed: %s",
                    self.session_id,
                    type(e).__name__,
                )
        finally:
            await self._cleanup()

    async def _dispatch(self, data: dict[str, Any]) -> None:
        """Route an incoming message to the appropriate handler.

        Humans can send: audio_data, leave_meeting, raise_hand,
        lower_hand, finished_speaking, get_queue, chat.
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
        elif msg_type == "raise_hand":
            await self._handle_raise_hand(RaiseHand.model_validate(data))
        elif msg_type == "lower_hand":
            await self._handle_lower_hand(LowerHand.model_validate(data))
        elif msg_type == "finished_speaking":
            await self._handle_finished_speaking(FinishedSpeaking.model_validate(data))
        elif msg_type == "get_queue":
            await self._handle_get_queue(GetQueue.model_validate(data))
        elif msg_type == "chat":
            await self._handle_chat(data)

    async def _handle_chat(self, data: dict[str, Any]) -> None:
        """Handle a chat message from the browser and broadcast to all participants.

        Args:
            data: Raw message dict with ``text`` field.
        """
        text = data.get("text", "").strip()
        if not text:
            return
        if self._manager.chat_bridge is not None:
            await self._manager.chat_bridge.handle_send_chat(
                meeting_id=self.meeting_id,
                sender_id=self._identity.agent_config_id,
                sender_name=self.agent_name,
                content=text,
            )

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
            await self._audio_bridge.process_audio(
                self.meeting_id, audio_bytes, speaker_name=self.agent_name
            )

        logger.info(
            "Received %d bytes of audio from human %s",
            len(audio_bytes),
            self.agent_name,
        )

    async def _handle_leave(self) -> None:
        """Handle a voluntary leave from the browser."""
        await self._leave_and_notify("voluntary")
        logger.info("Human %s left meeting %s", self.agent_name, self.meeting_id)

    async def _handle_raise_hand(self, msg: RaiseHand) -> None:
        """Handle a raise_hand request.

        Args:
            msg: The raise_hand message.
        """
        if self._manager.turn_bridge is None:
            await self._send_error("turn_unavailable", "Turn management is not available")
            return
        participant_id = self._identity.agent_config_id
        await self._manager.turn_bridge.handle_raise_hand(
            self.meeting_id,
            participant_id,
            priority=msg.priority,
            topic=msg.topic,
        )

    async def _handle_lower_hand(self, msg: LowerHand) -> None:
        """Handle a lower_hand request.

        Args:
            msg: The lower_hand message.
        """
        if self._manager.turn_bridge is None:
            return
        from uuid import UUID as _UUID

        participant_id = self._identity.agent_config_id
        hand_raise_id = _UUID(msg.hand_raise_id) if msg.hand_raise_id else None
        await self._manager.turn_bridge.handle_lower_hand(
            self.meeting_id,
            participant_id,
            hand_raise_id=hand_raise_id,
        )

    async def _handle_finished_speaking(self, msg: FinishedSpeaking) -> None:
        """Handle a finished_speaking request.

        Args:
            msg: The finished_speaking message.
        """
        if self._manager.turn_bridge is None:
            return
        participant_id = self._identity.agent_config_id
        await self._manager.turn_bridge.handle_finished_speaking(
            self.meeting_id,
            participant_id,
        )

    async def _handle_get_queue(self, msg: GetQueue) -> None:
        """Handle a get_queue request (responds to requester only).

        Args:
            msg: The get_queue message.
        """
        if self._manager.turn_bridge is None:
            payload = {"meeting_id": str(self.meeting_id), "active_speaker_id": None, "queue": []}
        else:
            payload = await self._manager.turn_bridge.get_queue_payload(self.meeting_id)
        await self.send_event("turn.queue.updated", payload)

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
        speaker_name: str | None = None,
    ) -> None:
        """Send a transcript segment to the browser.

        Args:
            meeting_id: The meeting the transcript belongs to.
            speaker_id: Speaker identifier.
            text: Transcribed text.
            start_time: Segment start time.
            end_time: Segment end time.
            confidence: STT confidence score.
            speaker_name: Human-readable display name of the speaker.
        """
        msg = TranscriptMessage(
            meeting_id=meeting_id,
            speaker_id=speaker_id,
            speaker_name=speaker_name,
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
        source: str | None = None,
    ) -> None:
        """Send a participant join/leave notification to the browser.

        Args:
            action: "joined" or "left".
            participant_id: The participant's ID.
            name: Display name.
            role: Participant role.
            connection_type: How they're connected.
            source: Connection source (e.g. "agent", "claude-code", "human").
        """
        msg = ParticipantUpdate(
            action=action,
            participant_id=participant_id,
            name=name,
            role=role,
            connection_type=connection_type,
            source=source,
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

    async def _broadcast_participant_update(self, action: str) -> None:
        """Broadcast a participant join/leave to all other sessions in this meeting.

        Args:
            action: "joined" or "left".
        """
        sessions = self._manager.get_meeting_sessions(self.meeting_id)
        for session in sessions:
            if session.session_id == self.session_id:
                continue
            try:
                await session.send_participant_update(
                    action=action,
                    participant_id=self._identity.agent_config_id,
                    name=self.agent_name,
                    role="human",
                    connection_type="websocket",
                )
            except Exception:
                logger.warning(
                    "Failed to send participant_update (%s) to session %s",
                    action,
                    session.session_id,
                )

    async def _publish_participant_event(self, action: str, reason: str = "normal") -> None:
        """Publish a participant.joined or participant.left event to Redis Streams.

        Args:
            action: "joined" or "left".
            reason: Reason for leaving (only used for "left" action).
        """
        if self._manager.redis is None:
            return

        from kutana_core.events.definitions import ParticipantJoined, ParticipantLeft

        if action == "joined":
            event: ParticipantJoined | ParticipantLeft = ParticipantJoined(
                participant_id=self._identity.agent_config_id,
                meeting_id=self.meeting_id,
                name=self.agent_name,
                role="human",
                connection_type="websocket",
            )
        else:
            event = ParticipantLeft(
                participant_id=self._identity.agent_config_id,
                meeting_id=self.meeting_id,
                reason=reason,
            )

        payload = json.dumps(event.to_dict(), default=str)
        try:
            await self._manager.redis.xadd(
                "kutana:events",
                {"event_type": event.event_type, "payload": payload},
                maxlen=10_000,
                approximate=True,
            )
        except Exception:
            logger.warning(
                "Failed to publish %s event for human %s",
                event.event_type,
                self.agent_name,
            )

    async def _leave_and_notify(self, reason: str = "normal") -> None:
        """Broadcast leave, publish event, and remove from meeting (idempotent).

        Args:
            reason: Reason for leaving (e.g. "voluntary", "disconnected").
        """
        if self._left_announced:
            return
        self._left_announced = True

        await self._broadcast_participant_update("left")
        await self._publish_participant_event("left", reason=reason)
        self._manager.leave_meeting(self.session_id, self.meeting_id)

    async def _cleanup(self) -> None:
        """Clean up session state on disconnect."""
        await self._leave_and_notify("disconnected")
        if self._audio_bridge is not None:
            await self._audio_bridge.close_pipeline(self.meeting_id)
        self._manager.unregister(self.session_id)
