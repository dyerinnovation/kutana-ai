"""Abstract base class for the portable message bus."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from convene_core.messaging.types import MessageHandler, Subscription


class MessageBus(ABC):
    """Abstract message bus for decoupled inter-service communication.

    Implementations support publish/subscribe semantics with optional consumer
    group load balancing and at-least-once delivery acknowledgment. Services
    depend only on this interface; the concrete backend is resolved at startup
    from the ``CONVENE_MESSAGE_BUS`` environment variable via the provider
    registry.

    Example:
        bus = RedisStreamsMessageBus()
        sub = await bus.subscribe("meeting.*.events", handler)
        msg_id = await bus.publish("meeting.abc.events", {"type": "started"})
        await bus.ack(sub, msg_id)
        await bus.close()
    """

    @abstractmethod
    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        metadata: dict[str, str] | None = None,
        source: str = "",
    ) -> str:
        """Publish a message to a topic.

        Args:
            topic: The topic to publish to. Maps 1:1 to a backend stream/queue.
            payload: The message payload (must be JSON-serializable).
            metadata: Optional routing and contextual metadata.
            source: Name of the service publishing this message.

        Returns:
            The unique message ID assigned to this message.
        """
        ...

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: MessageHandler,
        group: str | None = None,
    ) -> Subscription:
        """Subscribe to a topic.

        Args:
            topic: The topic or fnmatch pattern to subscribe to (e.g.,
                ``"meeting.*.events"`` matches any meeting's events topic).
            handler: Async callback invoked for each delivered message.
            group: Consumer group name for load-balanced delivery across
                multiple subscribers. None delivers to all subscribers.

        Returns:
            A Subscription object for use with :meth:`unsubscribe` and
            :meth:`ack`.
        """
        ...

    @abstractmethod
    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove an active subscription.

        After this call the handler will no longer be invoked for new messages.

        Args:
            subscription: The subscription to remove.
        """
        ...

    @abstractmethod
    async def ack(self, subscription: Subscription, message_id: str) -> None:
        """Acknowledge receipt of a message.

        Required for at-least-once delivery guarantees when using consumer
        groups. No-op for fan-out (non-group) subscriptions.

        Args:
            subscription: The subscription that received the message.
            message_id: The ID of the message to acknowledge.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the message bus and release all resources."""
        ...
