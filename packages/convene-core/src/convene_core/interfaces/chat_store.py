"""Chat store provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from convene_core.models.chat import ChatMessage, ChatMessageType


class ChatStore(ABC):
    """Abstract base class for meeting chat storage providers.

    Implementations manage message persistence and pub/sub delivery
    for a meeting's chat channel. Messages are stored in insertion order
    and retrievable with optional filters.

    All operations are scoped to a single meeting and are async-safe.
    """

    @abstractmethod
    async def send_message(
        self,
        meeting_id: UUID,
        sender_id: UUID,
        sender_name: str,
        content: str,
        message_type: ChatMessageType = ChatMessageType.TEXT,
    ) -> ChatMessage:
        """Store a chat message and notify subscribers.

        Args:
            meeting_id: The meeting this message belongs to.
            sender_id: The participant or agent sending the message.
            sender_name: Display name of the sender.
            content: The message text content.
            message_type: Semantic type classification (default: text).

        Returns:
            The stored ChatMessage with assigned message_id and sequence.
        """
        ...

    @abstractmethod
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
            limit: Maximum number of messages to return (default 50).
            message_type: Filter by message type — None returns all types.
            since: Only return messages sent after this UTC datetime.
                   When combined with limit, returns earliest `limit` messages
                   after `since`.

        Returns:
            List of ChatMessage in chronological order (oldest first).
        """
        ...

    @abstractmethod
    async def clear_meeting(self, meeting_id: UUID) -> None:
        """Clear all chat messages for a meeting.

        Should be called when a meeting ends to release storage resources.

        Args:
            meeting_id: The meeting to clear.
        """
        ...
