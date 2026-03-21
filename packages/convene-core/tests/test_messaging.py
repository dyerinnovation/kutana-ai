"""Tests for the convene-core messaging abstraction."""

from __future__ import annotations

from datetime import datetime

import pytest

from convene_core.messaging.abc import MessageBus
from convene_core.messaging.types import Message, Subscription

# ---------------------------------------------------------------------------
# Message model tests
# ---------------------------------------------------------------------------


class TestMessage:
    """Tests for the Message Pydantic model."""

    def test_defaults_are_generated(self) -> None:
        """Message auto-generates id, timestamp, and defaults."""
        msg = Message(topic="test.topic", payload={"key": "value"})
        assert isinstance(msg.id, str)
        assert len(msg.id) == 36  # UUID4 format
        assert isinstance(msg.timestamp, datetime)
        assert msg.timestamp.tzinfo is not None
        assert msg.metadata == {}
        assert msg.source == ""

    def test_explicit_fields_are_stored(self) -> None:
        """Explicitly provided fields are stored as-is."""
        msg = Message(
            topic="meeting.started",
            payload={"meeting_id": "abc"},
            metadata={"region": "us-east-1"},
            source="api-server",
        )
        assert msg.topic == "meeting.started"
        assert msg.payload == {"meeting_id": "abc"}
        assert msg.metadata == {"region": "us-east-1"}
        assert msg.source == "api-server"

    def test_unique_ids_generated(self) -> None:
        """Each Message instance receives a unique id."""
        ids = {Message(topic="t", payload={}).id for _ in range(20)}
        assert len(ids) == 20

    def test_serialization_roundtrip(self) -> None:
        """model_dump / model_validate round-trip preserves all fields."""
        msg = Message(
            topic="task.created",
            payload={"task_id": "xyz", "priority": 1},
            metadata={"correlation_id": "corr-123"},
            source="task-engine",
        )
        data = msg.model_dump()
        restored = Message.model_validate(data)
        assert restored.id == msg.id
        assert restored.topic == msg.topic
        assert restored.payload == msg.payload
        assert restored.metadata == msg.metadata
        assert restored.source == msg.source
        assert restored.timestamp == msg.timestamp

    def test_json_serialization(self) -> None:
        """model_dump(mode='json') produces JSON-serializable output."""
        msg = Message(topic="events", payload={"count": 3})
        data = msg.model_dump(mode="json")
        assert isinstance(data["id"], str)
        assert isinstance(data["timestamp"], str)
        assert data["topic"] == "events"

    def test_empty_payload_allowed(self) -> None:
        """An empty payload dict is valid."""
        msg = Message(topic="heartbeat", payload={})
        assert msg.payload == {}


# ---------------------------------------------------------------------------
# Subscription dataclass tests
# ---------------------------------------------------------------------------


class TestSubscription:
    """Tests for the Subscription dataclass."""

    async def test_defaults(self) -> None:
        """Subscription gets unique subscription_id and None group by default."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="test.topic", handler=handler)
        assert sub.topic == "test.topic"
        assert sub.group is None
        assert isinstance(sub.subscription_id, str)
        assert len(sub.subscription_id) == 36

    async def test_unique_subscription_ids(self) -> None:
        """Each Subscription instance receives a distinct subscription_id."""

        async def handler(msg: Message) -> None:
            pass

        subs = [Subscription(topic="t", handler=handler) for _ in range(10)]
        ids = {s.subscription_id for s in subs}
        assert len(ids) == 10

    async def test_group_stored(self) -> None:
        """Consumer group name is stored on the subscription."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="events", handler=handler, group="workers")
        assert sub.group == "workers"

    async def test_handler_is_callable(self) -> None:
        """The stored handler is callable."""
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        sub = Subscription(topic="t", handler=handler)
        msg = Message(topic="t", payload={})
        await sub.handler(msg)
        assert len(received) == 1
        assert received[0] is msg


# ---------------------------------------------------------------------------
# MessageBus ABC tests
# ---------------------------------------------------------------------------


class TestMessageBusABC:
    """Tests that MessageBus is properly abstract."""

    def test_cannot_instantiate_directly(self) -> None:
        """MessageBus raises TypeError when instantiated directly."""
        with pytest.raises(TypeError):
            MessageBus()  # type: ignore[abstract]

    def test_all_abstract_methods_declared(self) -> None:
        """All required interface methods are abstract."""
        abstract = MessageBus.__abstractmethods__
        assert "publish" in abstract
        assert "subscribe" in abstract
        assert "unsubscribe" in abstract
        assert "ack" in abstract
        assert "close" in abstract

    def test_concrete_subclass_must_implement_all_methods(self) -> None:
        """A subclass missing any abstract method cannot be instantiated."""

        class Incomplete(MessageBus):
            async def publish(self, topic: str, payload: dict, metadata: dict | None = None, source: str = "") -> str:  # type: ignore[override]
                return ""

            # Intentionally omitting subscribe, unsubscribe, ack, close

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# MockMessageBus tests (from convene_providers)
# ---------------------------------------------------------------------------


class TestMockMessageBus:
    """Integration smoke tests using MockMessageBus."""

    async def test_publish_records_message(self) -> None:
        """publish() appends to the published list."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()
        msg_id = await bus.publish("test.topic", {"x": 1})
        assert isinstance(msg_id, str)
        assert len(bus.published) == 1
        assert bus.published[0].topic == "test.topic"
        assert bus.published[0].payload == {"x": 1}

    async def test_subscribe_then_publish_dispatches(self) -> None:
        """Subscribers receive messages published after subscribing."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        await bus.subscribe("events", handler)
        await bus.publish("events", {"type": "started"})

        assert len(received) == 1
        assert received[0].payload == {"type": "started"}

    async def test_unsubscribe_stops_delivery(self) -> None:
        """After unsubscribe, handler no longer receives messages."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        sub = await bus.subscribe("events", handler)
        await bus.publish("events", {"n": 1})
        await bus.unsubscribe(sub)
        await bus.publish("events", {"n": 2})

        assert len(received) == 1

    async def test_pattern_subscription(self) -> None:
        """Subscriptions with fnmatch patterns match multiple topics."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()
        received: list[str] = []

        async def handler(msg: Message) -> None:
            received.append(msg.topic)

        await bus.subscribe("meeting.*.started", handler)
        await bus.publish("meeting.abc123.started", {})
        await bus.publish("meeting.xyz789.started", {})
        await bus.publish("meeting.abc123.ended", {})  # should NOT match

        assert "meeting.abc123.started" in received
        assert "meeting.xyz789.started" in received
        assert "meeting.abc123.ended" not in received

    async def test_ack_is_noop(self) -> None:
        """ack() does not raise on MockMessageBus."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("t", handler)
        await bus.ack(sub, "some-message-id")  # should not raise

    async def test_close_clears_subscriptions(self) -> None:
        """close() prevents further message delivery."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        await bus.subscribe("events", handler)
        await bus.close()
        await bus.publish("events", {})

        assert len(received) == 0

    async def test_multiple_subscribers_all_receive(self) -> None:
        """Multiple subscribers to the same topic all receive each message."""
        from convene_providers.testing import MockMessageBus

        bus = MockMessageBus()
        received_a: list[Message] = []
        received_b: list[Message] = []

        async def handler_a(msg: Message) -> None:
            received_a.append(msg)

        async def handler_b(msg: Message) -> None:
            received_b.append(msg)

        await bus.subscribe("events", handler_a)
        await bus.subscribe("events", handler_b)
        await bus.publish("events", {"x": 1})

        assert len(received_a) == 1
        assert len(received_b) == 1
