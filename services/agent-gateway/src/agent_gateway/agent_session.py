"""Per-agent session lifecycle management."""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from agent_gateway.protocol import (
    AudioData,
    DataMessage,
    ErrorMessage,
    EventMessage,
    FinishedSpeaking,
    GetQueue,
    Joined,
    JoinMeeting,
    LeaveMeeting,
    LowerHand,
    ParticipantUpdate,
    RaiseHand,
    TranscriptMessage,
    parse_client_message,
)

if TYPE_CHECKING:
    from fastapi import WebSocket
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from agent_gateway.audio_bridge import AudioBridge
    from agent_gateway.auth import AgentIdentity
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class AgentSessionHandler:
    """Manages the lifecycle of a single agent WebSocket connection.

    Handles message routing, audio forwarding, and event delivery
    for one connected agent.

    Attributes:
        session_id: Unique identifier for this session.
        agent_identity: Validated identity from JWT.
        meeting_id: Currently joined meeting (None if not in a meeting).
        capabilities: Granted capabilities for the current session.
        agent_name: Display name of the agent.
    """

    def __init__(
        self,
        websocket: WebSocket,
        identity: AgentIdentity,
        connection_manager: ConnectionManager,
        audio_bridge: AudioBridge | None = None,
        db_session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        """Initialise the session handler.

        Args:
            websocket: The WebSocket connection.
            identity: Validated agent identity from JWT.
            connection_manager: The global connection manager.
            audio_bridge: Optional AudioBridge for STT processing.
            db_session_factory: Optional async session factory for DB persistence.
        """
        self._ws = websocket
        self._identity = identity
        self._manager = connection_manager
        self._audio_bridge = audio_bridge
        self._db_factory = db_session_factory
        self.session_id: UUID = uuid4()
        self.agent_name: str = identity.name
        self.meeting_id: UUID | None = None
        self.capabilities: list[str] = []
        self.subscribed_channels: set[str] = set()
        self._connected_at: datetime = datetime.now(tz=UTC)

    async def handle(self) -> None:
        """Main message loop for the agent session.

        Reads messages from the WebSocket, dispatches to handlers,
        and cleans up on disconnect.
        """
        try:
            while True:
                raw = await self._ws.receive_text()
                data = json.loads(raw)
                await self._dispatch(data)
        except Exception as e:
            logger.info(
                "Agent session %s disconnected: %s",
                self.session_id,
                type(e).__name__,
            )
        finally:
            await self._cleanup()

    async def _dispatch(self, data: dict[str, Any]) -> None:
        """Route an incoming message to the appropriate handler.

        Args:
            data: Raw parsed message dict.
        """
        try:
            msg = parse_client_message(data)
        except ValueError as e:
            await self._send_error("invalid_message", str(e))
            return

        if isinstance(msg, JoinMeeting):
            await self._handle_join(msg)
        elif isinstance(msg, AudioData):
            await self._handle_audio(msg)
        elif isinstance(msg, DataMessage):
            await self._handle_data(msg)
        elif isinstance(msg, LeaveMeeting):
            await self._handle_leave(msg)
        elif isinstance(msg, RaiseHand):
            await self._handle_raise_hand(msg)
        elif isinstance(msg, LowerHand):
            await self._handle_lower_hand(msg)
        elif isinstance(msg, FinishedSpeaking):
            await self._handle_finished_speaking(msg)
        elif isinstance(msg, GetQueue):
            await self._handle_get_queue(msg)

    async def _handle_join(self, msg: JoinMeeting) -> None:
        """Handle a join_meeting request.

        Args:
            msg: The join meeting message.
        """
        if self.meeting_id is not None:
            await self._send_error(
                "already_joined",
                "Already in a meeting. Leave first.",
            )
            return

        # Grant capabilities based on intersection of requested and allowed
        allowed = set(self._identity.capabilities)
        requested = set(msg.capabilities)
        self.capabilities = list(allowed & requested) or list(allowed)

        self.meeting_id = msg.meeting_id
        self._manager.join_meeting(self.session_id, msg.meeting_id)

        if self._audio_bridge is not None:
            await self._audio_bridge.ensure_pipeline(msg.meeting_id)

        # Persist agent session record
        await self._persist_join(msg.meeting_id)

        response = Joined(
            meeting_id=msg.meeting_id,
            granted_capabilities=self.capabilities,
        )
        await self._send(response.model_dump(mode="json"))
        logger.info(
            "Agent %s joined meeting %s with capabilities %s",
            self.agent_name,
            msg.meeting_id,
            self.capabilities,
        )

    async def _handle_audio(self, msg: AudioData) -> None:
        """Handle incoming audio data from the agent.

        Decodes base64 PCM16 and could forward to AudioPipeline.

        Args:
            msg: The audio data message.
        """
        if self.meeting_id is None:
            await self._send_error("not_in_meeting", "Join a meeting first")
            return

        if "speak" not in self.capabilities:
            await self._send_error(
                "capability_denied",
                "Agent does not have 'speak' capability",
            )
            return

        try:
            audio_bytes = base64.b64decode(msg.data)
        except Exception:
            await self._send_error("invalid_audio", "Invalid base64 audio data")
            return

        if self._audio_bridge is not None:
            await self._audio_bridge.process_audio(self.meeting_id, audio_bytes)

        logger.debug(
            "Received %d bytes of audio from agent %s",
            len(audio_bytes),
            self.agent_name,
        )

    async def _handle_data(self, msg: DataMessage) -> None:
        """Handle structured data from the agent.

        Publishes the data to Redis for routing to other agents in the
        same meeting, filtered by channel and capabilities.

        Args:
            msg: The data message.
        """
        if self.meeting_id is None:
            await self._send_error("not_in_meeting", "Join a meeting first")
            return

        # Publish data to Redis Streams for channel-based routing
        if self._manager.redis is not None:
            import json as _json

            event_payload = _json.dumps({
                "meeting_id": str(self.meeting_id),
                "sender_session_id": str(self.session_id),
                "sender_name": self.agent_name,
                "channel": msg.channel,
                "payload": msg.payload,
            })
            try:
                await self._manager.redis.xadd(
                    "convene:events",
                    {
                        "event_type": f"data.channel.{msg.channel}",
                        "payload": event_payload,
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to publish data channel event for %s",
                    self.agent_name,
                )

        logger.debug(
            "Data from agent %s on channel %s",
            self.agent_name,
            msg.channel,
        )

    async def _handle_leave(self, msg: LeaveMeeting) -> None:
        """Handle a leave_meeting request.

        Args:
            msg: The leave meeting message.
        """
        if self.meeting_id is not None:
            if self._audio_bridge is not None:
                await self._audio_bridge.close_pipeline(self.meeting_id)
            self._manager.leave_meeting(self.session_id, self.meeting_id)
            await self._persist_leave()
            logger.info(
                "Agent %s left meeting %s: %s",
                self.agent_name,
                self.meeting_id,
                msg.reason,
            )
            self.meeting_id = None
            self.capabilities = []

    async def _handle_raise_hand(self, msg: RaiseHand) -> None:
        """Handle a raise_hand request from the agent.

        Args:
            msg: The raise_hand message.
        """
        if self.meeting_id is None:
            await self._send_error("not_in_meeting", "Join a meeting first")
            return
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
        """Handle a lower_hand request from the agent.

        Args:
            msg: The lower_hand message.
        """
        if self.meeting_id is None:
            return
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
        """Handle a finished_speaking request from the agent.

        Args:
            msg: The finished_speaking message.
        """
        if self.meeting_id is None:
            return
        if self._manager.turn_bridge is None:
            return
        participant_id = self._identity.agent_config_id
        await self._manager.turn_bridge.handle_finished_speaking(
            self.meeting_id,
            participant_id,
        )

    async def _handle_get_queue(self, msg: GetQueue) -> None:
        """Handle a get_queue request from the agent (responds to requester only).

        Args:
            msg: The get_queue message.
        """
        if self.meeting_id is None:
            return
        if self._manager.turn_bridge is None:
            payload: dict[str, Any] = {
                "meeting_id": str(self.meeting_id),
                "active_speaker_id": None,
                "queue": [],
            }
        else:
            payload = await self._manager.turn_bridge.get_queue_payload(self.meeting_id)
        await self.send_event("turn.queue.updated", payload)

    async def send_transcript(
        self,
        meeting_id: UUID,
        speaker_id: str | None,
        text: str,
        start_time: float,
        end_time: float,
        confidence: float,
    ) -> None:
        """Send a transcript segment to the agent.

        Args:
            meeting_id: The meeting the transcript belongs to.
            speaker_id: Speaker identifier.
            text: Transcribed text.
            start_time: Segment start time.
            end_time: Segment end time.
            confidence: STT confidence score.
        """
        if "listen" not in self.capabilities and "transcribe" not in self.capabilities:
            return

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
        """Send a domain event to the agent.

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
        """Send a participant update to the agent.

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
        """Send a JSON message to the agent.

        Args:
            data: Message dict to serialize and send.
        """
        try:
            await self._ws.send_json(data)
        except Exception:
            logger.warning(
                "Failed to send message to agent %s",
                self.agent_name,
            )

    async def _send_error(self, code: str, message: str) -> None:
        """Send an error message to the agent.

        Args:
            code: Error code string.
            message: Human-readable error message.
        """
        err = ErrorMessage(code=code, message=message)
        await self._send(err.model_dump(mode="json"))

    async def _cleanup(self) -> None:
        """Clean up session state on disconnect."""
        if self.meeting_id is not None:
            if self._audio_bridge is not None:
                await self._audio_bridge.close_pipeline(self.meeting_id)
            self._manager.leave_meeting(self.session_id, self.meeting_id)
            await self._persist_leave()
        self._manager.unregister(self.session_id)

    # ------------------------------------------------------------------
    # Database persistence helpers
    # ------------------------------------------------------------------

    async def _persist_join(self, meeting_id: UUID) -> None:
        """Create an AgentSessionORM record when joining a meeting.

        Args:
            meeting_id: The meeting being joined.
        """
        if self._db_factory is None:
            return

        try:
            from convene_core.database.models import AgentSessionORM

            async with self._db_factory() as db:
                record = AgentSessionORM(
                    id=self.session_id,
                    agent_config_id=self._identity.agent_config_id,
                    meeting_id=meeting_id,
                    connection_type="agent_gateway",
                    capabilities=self.capabilities,
                    status="active",
                    connected_at=datetime.now(tz=UTC),
                )
                db.add(record)
                await db.commit()
                logger.debug(
                    "Persisted agent session %s (join)", self.session_id
                )
        except Exception:
            logger.exception(
                "Failed to persist agent session join for %s", self.session_id
            )

    async def _persist_leave(self) -> None:
        """Update AgentSessionORM record when leaving a meeting."""
        if self._db_factory is None:
            return

        try:
            from sqlalchemy import update

            from convene_core.database.models import AgentSessionORM

            async with self._db_factory() as db:
                await db.execute(
                    update(AgentSessionORM)
                    .where(AgentSessionORM.id == self.session_id)
                    .values(
                        status="disconnected",
                        disconnected_at=datetime.now(tz=UTC),
                    )
                )
                await db.commit()
                logger.debug(
                    "Persisted agent session %s (leave)", self.session_id
                )
        except Exception:
            logger.exception(
                "Failed to persist agent session leave for %s", self.session_id
            )
