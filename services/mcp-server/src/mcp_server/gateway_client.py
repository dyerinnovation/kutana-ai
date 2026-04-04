"""WebSocket client for the Kutana Agent Gateway.

Reuses the battle-tested connection pattern from scripts/test_e2e_gateway.py.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed as _WsConnectionClosed

logger = logging.getLogger(__name__)


class GatewayClient:
    """WebSocket client that connects to the Kutana Agent Gateway.

    Manages the lifecycle of a gateway connection: connect, join meeting,
    buffer incoming transcript messages, and disconnect.

    Attributes:
        gateway_ws_url: Gateway WebSocket base URL.
        token: Gateway JWT for authentication.
    """

    def __init__(self, gateway_ws_url: str, token: str) -> None:
        self.gateway_ws_url = gateway_ws_url.rstrip("/")
        self.token = token
        self._ws: websockets.WebSocketClientProtocol | None = None  # type: ignore[name-defined]
        self._transcript_buffer: list[dict[str, Any]] = []
        self._channel_buffer: dict[str, list[dict[str, Any]]] = {}
        self._events_buffer: list[dict[str, Any]] = []  # turn, participant, chat WS events
        self._listener_task: asyncio.Task[None] | None = None
        self._meeting_id: str | None = None
        self._participants: list[dict[str, Any]] = []
        self.subscribed_channels: set[str] = set()

    async def connect_and_join(
        self,
        meeting_id: str,
        capabilities: list[str] | None = None,
        source: str = "claude-code",
        tts_enabled: bool = False,
        tts_voice: str | None = None,
    ) -> dict[str, Any]:
        """Connect to the gateway and join a meeting.

        Args:
            meeting_id: UUID of the meeting to join.
            capabilities: Requested capabilities list.
            source: Connection source identifier sent in the join message.
            tts_enabled: Set True for TTS-capable agents that will send spoken_text.
            tts_voice: Preferred voice ID; assigned from pool if None.

        Returns:
            The 'joined' response message from the gateway.

        Raises:
            RuntimeError: If connection or join fails.
        """
        if capabilities is None:
            capabilities = ["listen", "transcribe"]

        ws_url = f"{self.gateway_ws_url}/agent/connect?token={self.token}"
        logger.info("Connecting to gateway: %s", self.gateway_ws_url)

        self._ws = await websockets.connect(ws_url)
        logger.info("Connected. Joining meeting %s...", meeting_id)

        join_msg: dict[str, Any] = {
            "type": "join_meeting",
            "meeting_id": meeting_id,
            "capabilities": capabilities,
            "source": source,
            "tts_enabled": tts_enabled,
        }
        if tts_voice is not None:
            join_msg["tts_voice"] = tts_voice
        await self._ws.send(json.dumps(join_msg))

        raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
        response = json.loads(raw)

        if response.get("type") != "joined":
            raise RuntimeError(f"Failed to join meeting: {response}")

        self._meeting_id = meeting_id
        logger.info("Joined meeting %s", meeting_id)

        # Start background listener for transcript messages
        self._listener_task = asyncio.create_task(self._listen())
        return response

    # Event types that are buffered in _events_buffer for polling via get_meeting_events()
    _BUFFERED_EVENT_TYPES = frozenset({
        "turn_queue_updated",
        "turn_speaker_changed",
        "turn_your_turn",
        "participant_update",
        "chat_message",
    })

    async def _listen(self) -> None:
        """Background listener that buffers incoming gateway messages."""
        if self._ws is None:
            return

        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "transcript":
                    self._transcript_buffer.append(msg)
                    logger.debug(
                        "Transcript: [%.1f-%.1fs] %s",
                        msg.get("start_time", 0),
                        msg.get("end_time", 0),
                        msg.get("text", ""),
                    )
                elif msg_type == "event":
                    event_type = msg.get("event_type", "unknown")
                    if event_type == "participant_joined":
                        self._participants.append(msg.get("data", {}))
                    # Buffer data channel events
                    if event_type.startswith("data.channel."):
                        channel = event_type.removeprefix("data.channel.")
                        if channel in self.subscribed_channels or "*" in self.subscribed_channels:
                            if channel not in self._channel_buffer:
                                self._channel_buffer[channel] = []
                            self._channel_buffer[channel].append(msg.get("payload", {}))
                    logger.debug("Event: %s", event_type)
                elif msg_type in self._BUFFERED_EVENT_TYPES:
                    # Buffer turn management, participant, and chat events pushed by the gateway
                    self._events_buffer.append(msg)
                    if msg_type == "participant_update":
                        action = msg.get("action")
                        participant = {
                            "participant_id": msg.get("participant_id"),
                            "name": msg.get("name"),
                            "role": msg.get("role"),
                            "connection_type": msg.get("connection_type"),
                            "source": msg.get("source"),
                        }
                        if action == "joined":
                            self._participants.append(participant)
                        elif action == "left":
                            self._participants = [
                                p for p in self._participants
                                if p.get("participant_id") != msg.get("participant_id")
                            ]
                    logger.debug("Buffered gateway event: %s", msg_type)
                elif msg_type == "error":
                    logger.error(
                        "Gateway error: [%s] %s",
                        msg.get("code"),
                        msg.get("message"),
                    )
        except _WsConnectionClosed:
            logger.info("Gateway connection closed")
        except Exception:
            logger.exception("Error in gateway listener")

    def get_transcript(self, last_n: int = 50) -> list[dict[str, Any]]:
        """Get recent transcript segments from the buffer.

        Args:
            last_n: Maximum number of recent segments to return.

        Returns:
            List of transcript message dicts.
        """
        return self._transcript_buffer[-last_n:]

    def get_participants(self) -> list[dict[str, Any]]:
        """Get the list of known meeting participants.

        Returns:
            List of participant dicts.
        """
        return self._participants

    def subscribe_channel(self, channel: str) -> None:
        """Subscribe to a data channel.

        Registers the channel locally and sends a subscribe_channel message to the
        gateway so the server-side session routes data.channel.* events here.

        Args:
            channel: Channel name to subscribe to.
        """
        self.subscribed_channels.add(channel)
        if channel not in self._channel_buffer:
            self._channel_buffer[channel] = []

        # Notify the gateway of the subscription (fire-and-forget via task)
        if self._ws is not None:
            import asyncio

            subscribe_msg = json.dumps({
                "type": "subscribe_channel",
                "channels": [channel],
            })
            _task = asyncio.create_task(self._ws.send(subscribe_msg))  # noqa: RUF006

        logger.info("Subscribed to channel: %s", channel)

    async def start_speaking(self) -> None:
        """Send a start_speaking signal to the gateway.

        Activates TTS mode (for tts_enabled agents) and transitions the
        agent's turn state from "your_turn" to "actively_speaking".

        Raises:
            RuntimeError: If not connected to the gateway.
        """
        if self._ws is None:
            raise RuntimeError("Not connected to gateway")
        await self._ws.send(json.dumps({"type": "start_speaking"}))
        logger.debug("Sent start_speaking to gateway")

    async def send_spoken_text(self, text: str) -> None:
        """Send a spoken_text message to the gateway for TTS synthesis.

        The gateway will synthesize the text using the configured TTS provider
        and broadcast the resulting audio as tts.audio events to all meeting
        participants that have the listen capability.

        Must be preceded by start_speaking() to activate TTS mode.

        Args:
            text: The text to synthesize and broadcast.

        Raises:
            RuntimeError: If not connected to the gateway.
        """
        if self._ws is None:
            raise RuntimeError("Not connected to gateway")
        await self._ws.send(json.dumps({"type": "spoken_text", "text": text}))
        logger.debug("Sent spoken_text (%d chars) to gateway", len(text))

    async def stop_speaking(self) -> None:
        """Send a stop_speaking signal to the gateway.

        Deactivates TTS mode and signals that the agent has finished its turn.

        Raises:
            RuntimeError: If not connected to the gateway.
        """
        if self._ws is None:
            raise RuntimeError("Not connected to gateway")
        await self._ws.send(json.dumps({"type": "stop_speaking"}))
        logger.debug("Sent stop_speaking to gateway")

    async def publish_to_channel(
        self, channel: str, payload: dict[str, Any]
    ) -> None:
        """Publish a message to a data channel via the gateway.

        Args:
            channel: Channel name to publish to.
            payload: Data to publish.
        """
        if self._ws is None:
            raise RuntimeError("Not connected to gateway")

        data_msg = {
            "type": "data",
            "channel": channel,
            "payload": payload,
        }
        await self._ws.send(json.dumps(data_msg))
        logger.debug("Published to channel %s", channel)

    def get_events(
        self, last_n: int = 50, event_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get recent meeting events buffered from the gateway WebSocket.

        Includes turn queue updates, speaker changes, participant joins/leaves,
        and chat messages pushed directly by the gateway.

        Args:
            last_n: Maximum number of recent events to return.
            event_type: Optional filter — one of "turn_queue_updated",
                        "turn_speaker_changed", "turn_your_turn",
                        "participant_update", "chat_message".

        Returns:
            List of event message dicts.
        """
        if event_type is not None:
            filtered = [e for e in self._events_buffer if e.get("type") == event_type]
            return filtered[-last_n:]
        return self._events_buffer[-last_n:]

    def get_channel_messages(
        self, channel: str, last_n: int = 50
    ) -> list[dict[str, Any]]:
        """Get buffered messages from a data channel.

        Args:
            channel: Channel name.
            last_n: Maximum number of messages to return.

        Returns:
            List of channel message dicts.
        """
        buffer = self._channel_buffer.get(channel, [])
        return buffer[-last_n:]

    @property
    def meeting_id(self) -> str | None:
        """The current meeting ID, if connected."""
        return self._meeting_id

    async def leave(self) -> None:
        """Leave the current meeting and disconnect."""
        if self._ws is not None:
            try:
                leave_msg = {"type": "leave_meeting", "reason": "agent_disconnect"}
                await self._ws.send(json.dumps(leave_msg))
            except Exception:
                pass
            await self._ws.close()
            self._ws = None

        if self._listener_task is not None:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        self._meeting_id = None
        logger.info("Left meeting and disconnected from gateway")
