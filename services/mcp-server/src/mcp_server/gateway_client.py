"""WebSocket client for the Convene Agent Gateway.

Reuses the battle-tested connection pattern from scripts/test_e2e_gateway.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class GatewayClient:
    """WebSocket client that connects to the Convene Agent Gateway.

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
        self._listener_task: asyncio.Task[None] | None = None
        self._meeting_id: str | None = None
        self._participants: list[dict[str, Any]] = []
        self.subscribed_channels: set[str] = set()

    async def connect_and_join(
        self,
        meeting_id: str,
        capabilities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Connect to the gateway and join a meeting.

        Args:
            meeting_id: UUID of the meeting to join.
            capabilities: Requested capabilities list.

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

        join_msg = {
            "type": "join_meeting",
            "meeting_id": meeting_id,
            "capabilities": capabilities,
        }
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

    async def _listen(self) -> None:
        """Background listener that buffers incoming transcript messages."""
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
                elif msg_type == "error":
                    logger.error(
                        "Gateway error: [%s] %s",
                        msg.get("code"),
                        msg.get("message"),
                    )
        except websockets.exceptions.ConnectionClosed:
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

        Args:
            channel: Channel name to subscribe to.
        """
        self.subscribed_channels.add(channel)
        if channel not in self._channel_buffer:
            self._channel_buffer[channel] = []
        logger.info("Subscribed to channel: %s", channel)

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
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        self._meeting_id = None
        logger.info("Left meeting and disconnected from gateway")
