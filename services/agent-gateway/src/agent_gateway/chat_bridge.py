"""Chat bridge for the agent gateway.

Wraps a ChatStore and broadcasts chat.message.received events to all
WebSocket participants in a meeting. Subscribes to a Redis Pub/Sub channel
so that messages sent from external sources (e.g., the MCP server) are
also delivered in real time to gateway-connected participants.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

import redis.asyncio as aioredis

from kutana_core.models.chat import ChatMessageType

if TYPE_CHECKING:
    from kutana_core.interfaces.chat_store import ChatStore
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Must match the channel used by RedisChatStore
_CHAT_PUBSUB_CHANNEL = "kutana:chat"


class ChatBridge:
    """Bridges ChatStore and the gateway connection manager.

    Responsibilities:
    1. Store messages via ChatStore when a WS-connected participant sends chat.
    2. Subscribe to Redis Pub/Sub so messages from any source (including MCP
       tools) trigger a broadcast to WS participants.
    3. Broadcast ``chat.message.received`` events to all sessions in a meeting.

    The pub/sub subscriber is the single broadcast path — WS-initiated sends
    go through ChatStore (which publishes to pub/sub), and the subscriber
    loop picks them up along with MCP-initiated sends.

    Attributes:
        chat_store: The underlying ChatStore provider.
        manager: The gateway's ConnectionManager for session access.
    """

    def __init__(
        self,
        chat_store: ChatStore,
        manager: ConnectionManager,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """Initialise the chat bridge.

        Args:
            chat_store: The chat storage provider.
            manager: The gateway connection manager.
            redis_url: Redis URL for the Pub/Sub subscriber connection.
        """
        self.chat_store = chat_store
        self.manager = manager
        self._redis_url = redis_url
        self._pubsub_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Redis Pub/Sub subscriber for real-time broadcast."""
        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(
                self._pubsub_loop(),
                name="chat-bridge-pubsub",
            )
            logger.info("ChatBridge pub/sub subscriber started")

    async def stop(self) -> None:
        """Stop the pub/sub subscriber and close the ChatStore."""
        if self._pubsub_task and not self._pubsub_task.done():
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        if hasattr(self.chat_store, "close"):
            await self.chat_store.close()  # type: ignore[attr-defined]
        logger.info("ChatBridge stopped")

    # ------------------------------------------------------------------
    # Action handlers — called from WS session dispatch
    # ------------------------------------------------------------------

    async def handle_send_chat(
        self,
        meeting_id: UUID,
        sender_id: UUID,
        sender_name: str,
        content: str,
        message_type: str = "text",
    ) -> None:
        """Handle a send_chat message from a WebSocket-connected participant.

        Stores the message via ChatStore, which publishes to Redis Pub/Sub.
        The pub/sub subscriber loop picks up the notification and broadcasts
        ``chat.message.received`` to all WS participants in the meeting.

        Args:
            meeting_id: The meeting.
            sender_id: The sending participant's UUID.
            sender_name: Display name of the sender.
            content: The message text.
            message_type: Semantic type ("text", "question", "action_item", "decision").
        """
        msg_type = ChatMessageType(message_type)
        await self.chat_store.send_message(
            meeting_id=meeting_id,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            message_type=msg_type,
        )
        # Broadcast is handled by the pub/sub loop after ChatStore publishes

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    async def _broadcast_message(
        self,
        meeting_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast a chat.message.received event to all WS participants.

        Args:
            meeting_id: The meeting to broadcast to.
            payload: Serialisable message payload from the pub/sub notification.
        """
        sender_session_id = payload.get("sender_session_id")
        sessions = self.manager.get_meeting_sessions(meeting_id)
        for session in sessions:
            if sender_session_id and str(session.session_id) == sender_session_id:
                continue
            try:
                await session.send_event("chat.message.received", payload)
            except Exception:
                logger.warning(
                    "Failed to send chat event to session %s",
                    session.session_id,
                )

    # ------------------------------------------------------------------
    # Redis Pub/Sub subscriber loop
    # ------------------------------------------------------------------

    async def _pubsub_loop(self) -> None:
        """Subscribe to Redis Pub/Sub and relay chat messages to WS participants.

        Runs until cancelled. Uses a dedicated Redis connection for subscribe
        mode (required by Redis — subscribing clients cannot issue other commands).
        """
        redis_client: aioredis.Redis = aioredis.from_url(  # type: ignore[type-arg]
            self._redis_url, decode_responses=True
        )
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(_CHAT_PUBSUB_CHANNEL)
        logger.info("ChatBridge subscribed to Redis Pub/Sub channel: %s", _CHAT_PUBSUB_CHANNEL)

        try:
            async for raw_msg in pubsub.listen():
                if raw_msg["type"] != "message":
                    continue
                try:
                    data: dict[str, Any] = json.loads(raw_msg["data"])
                    meeting_id = UUID(data["meeting_id"])
                    await self._broadcast_message(meeting_id, data)
                except (KeyError, ValueError, json.JSONDecodeError) as exc:
                    logger.warning("Malformed chat pub/sub message: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unexpected error in chat pub/sub loop")
        finally:
            await pubsub.unsubscribe(_CHAT_PUBSUB_CHANNEL)
            await redis_client.aclose()
            logger.debug("ChatBridge pub/sub subscriber closed")
