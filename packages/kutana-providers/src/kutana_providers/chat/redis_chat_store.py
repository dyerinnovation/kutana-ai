"""Redis-backed chat store provider.

Uses Redis Streams for durable ordered message storage and Redis Pub/Sub
for real-time delivery notifications to connected participants.

Key schema:
    kutana:{meeting_id}:chat:messages   STREAM  per-message fields stored as hash
        Fields: message_id, sender_id, sender_name, content, message_type, sent_at

Pub/sub channel:
    kutana:chat  — per-message notifications (JSON payload includes meeting_id)

The ``kutana:{meeting_id}:`` namespace prefix ensures that all meeting data
is isolated by meeting ID at the Redis key level, preventing cross-meeting
data access even if a caller has direct Redis access.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import redis.asyncio as aioredis

from kutana_core.interfaces.chat_store import ChatStore
from kutana_core.models.chat import ChatMessage, ChatMessageType

logger = logging.getLogger(__name__)

# Redis Pub/Sub channel for real-time chat delivery
CHAT_PUBSUB_CHANNEL = "kutana:chat"


class RedisChatStore(ChatStore):
    """Redis Streams-backed implementation of ChatStore.

    Stores messages in a per-meeting Redis Stream for durable ordered
    storage and publishes a notification to a Pub/Sub channel on each
    write so that the gateway can broadcast to WebSocket participants.

    Args:
        redis_url: Redis connection URL (e.g., "redis://localhost:6379/0").
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        """Initialise the Redis chat store.

        Args:
            redis_url: Redis connection URL.
        """
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None  # type: ignore[type-arg]

    async def _get_redis(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Return (and lazily initialise) the Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    @staticmethod
    def _stream_key(meeting_id: UUID) -> str:
        return f"kutana:{meeting_id}:chat:messages"

    # ------------------------------------------------------------------
    # ChatStore interface
    # ------------------------------------------------------------------

    async def send_message(
        self,
        meeting_id: UUID,
        sender_id: UUID,
        sender_name: str,
        content: str,
        message_type: ChatMessageType = ChatMessageType.TEXT,
    ) -> ChatMessage:
        """Store a chat message and notify pub/sub subscribers.

        Args:
            meeting_id: The meeting this message belongs to.
            sender_id: The participant or agent sending the message.
            sender_name: Display name of the sender.
            content: The message text content.
            message_type: Semantic type classification.

        Returns:
            The stored ChatMessage with assigned message_id and sequence.
        """
        r = await self._get_redis()
        message_id = uuid4()
        sent_at = datetime.now(tz=UTC)
        stream_key = self._stream_key(meeting_id)

        # Store in Redis Stream — entry ID is auto-generated as "ts_ms-seq"
        stream_entry_id: str = await r.xadd(
            stream_key,
            {
                "message_id": str(message_id),
                "sender_id": str(sender_id),
                "sender_name": sender_name,
                "content": content,
                "message_type": message_type.value,
                "sent_at": sent_at.isoformat(),
            },
        )

        # Extract millisecond timestamp from stream entry ID for sequence ordering
        sequence = int(stream_entry_id.split("-")[0])

        msg = ChatMessage(
            message_id=message_id,
            meeting_id=meeting_id,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            message_type=message_type,
            sent_at=sent_at,
            sequence=sequence,
        )

        # Publish notification for real-time delivery to gateway subscribers
        notification = json.dumps(
            {
                "meeting_id": str(meeting_id),
                "message_id": str(message_id),
                "sender_id": str(sender_id),
                "sender_name": sender_name,
                "content": content,
                "message_type": message_type.value,
                "sent_at": sent_at.isoformat(),
                "sequence": sequence,
            }
        )
        await r.publish(CHAT_PUBSUB_CHANNEL, notification)

        logger.info(
            "Chat message stored: %s in meeting %s from %s (%s)",
            message_id,
            meeting_id,
            sender_name,
            message_type.value,
        )
        return msg

    async def get_messages(
        self,
        meeting_id: UUID,
        limit: int = 50,
        message_type: ChatMessageType | None = None,
        since: datetime | None = None,
    ) -> list[ChatMessage]:
        """Retrieve chat messages for a meeting in chronological order.

        Args:
            meeting_id: The meeting to query.
            limit: Maximum number of messages to return.
            message_type: Filter by type — None returns all types.
            since: Return messages after this UTC datetime.

        Returns:
            List of ChatMessage in chronological order (oldest first).
        """
        r = await self._get_redis()
        stream_key = self._stream_key(meeting_id)

        if since is not None:
            # Forward range starting from the given timestamp
            since_ms = int(since.timestamp() * 1000)
            start_id = f"{since_ms}-0"
            raw_entries: list[tuple[str, dict[str, str]]] = await r.xrange(
                stream_key, min=start_id, max="+", count=limit
            )
        else:
            # Most recent `limit` messages in reverse, then re-reversed for chronological order.
            # Fetch more than `limit` when filtering by type to ensure we have enough after filtering.
            fetch_count = limit if message_type is None else limit * 4
            raw_entries = await r.xrevrange(stream_key, max="+", min="-", count=fetch_count)
            raw_entries = list(reversed(raw_entries))

        messages: list[ChatMessage] = []
        for entry_id, fields in raw_entries:
            try:
                msg_type = ChatMessageType(fields.get("message_type", "text"))

                # Apply optional message_type filter
                if message_type is not None and msg_type != message_type:
                    continue

                sequence = int(entry_id.split("-")[0])
                msg = ChatMessage(
                    message_id=UUID(fields["message_id"]),
                    meeting_id=meeting_id,
                    sender_id=UUID(fields["sender_id"]),
                    sender_name=fields["sender_name"],
                    content=fields["content"],
                    message_type=msg_type,
                    sent_at=datetime.fromisoformat(fields["sent_at"]),
                    sequence=sequence,
                )
                messages.append(msg)

                # Stop once we have `limit` after filtering
                if len(messages) >= limit:
                    break

            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed chat stream entry %s: %s", entry_id, exc)

        return messages

    async def clear_meeting(self, meeting_id: UUID) -> None:
        """Clear all chat messages for a meeting.

        Args:
            meeting_id: The meeting to clear.
        """
        r = await self._get_redis()
        stream_key = self._stream_key(meeting_id)
        await r.delete(stream_key)
        logger.info("Cleared chat messages for meeting %s", meeting_id)
