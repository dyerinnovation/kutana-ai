"""Unit tests for task-engine EventPublisher.

All tests use a mocked Redis client — no live Redis connection is made.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from task_engine.event_publisher import STREAM_KEY, EventPublisher

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_publisher() -> tuple[EventPublisher, AsyncMock]:
    """Build an EventPublisher with a mocked Redis client.

    Returns:
        Tuple of (publisher, mock_redis).
    """
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="1234567890-0")

    with patch("task_engine.event_publisher.redis") as mock_redis_module:
        mock_redis_module.from_url.return_value = mock_redis
        publisher = EventPublisher(redis_url="redis://localhost:6379/0")

    # Replace internal client directly so mock is used in tests
    publisher._redis = mock_redis
    return publisher, mock_redis


# ---------------------------------------------------------------------------
# EventPublisher — publish
# ---------------------------------------------------------------------------


class TestEventPublisherPublish:
    """Tests for EventPublisher.publish."""

    async def test_publish_calls_xadd(self) -> None:
        """publish() calls redis.xadd with the correct stream key."""
        from datetime import UTC, datetime

        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Fix the bug",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        await publisher.publish(event)

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == STREAM_KEY

    async def test_publish_includes_event_type_field(self) -> None:
        """Stream entry includes the correct event_type field."""
        from datetime import UTC, datetime

        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Finish the report",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        await publisher.publish(event)

        fields = mock_redis.xadd.call_args[0][1]
        assert fields["event_type"] == "task.created"

    async def test_publish_payload_is_valid_json(self) -> None:
        """The payload field is valid JSON containing event data."""
        from datetime import UTC, datetime

        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_publisher()

        task_id = uuid4()
        task = Task(
            id=task_id,
            meeting_id=uuid4(),
            description="Deploy to production",
            priority=TaskPriority.CRITICAL,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        await publisher.publish(event)

        fields = mock_redis.xadd.call_args[0][1]
        data = json.loads(fields["payload"])
        assert data["event_type"] == "task.created"
        assert data["task"]["id"] == str(task_id)

    async def test_publish_returns_entry_id(self) -> None:
        """publish() returns the Redis entry ID from xadd."""
        from datetime import UTC, datetime

        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_publisher()
        mock_redis.xadd.return_value = "9999999999-0"

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Write docs",
            priority=TaskPriority.LOW,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        entry_id = await publisher.publish(event)
        assert entry_id == "9999999999-0"

    async def test_publish_task_updated_event(self) -> None:
        """publish() works correctly for task.updated events."""
        from datetime import UTC, datetime

        from kutana_core.events.definitions import TaskUpdated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Review PR",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.DONE,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskUpdated(task=task, previous_status=TaskStatus.IN_PROGRESS)

        await publisher.publish(event)

        fields = mock_redis.xadd.call_args[0][1]
        assert fields["event_type"] == "task.updated"
        data = json.loads(fields["payload"])
        assert data["previous_status"] == "in_progress"


# ---------------------------------------------------------------------------
# EventPublisher — close
# ---------------------------------------------------------------------------


class TestEventPublisherClose:
    """Tests for EventPublisher.close."""

    async def test_close_calls_aclose(self) -> None:
        """close() calls aclose() on the Redis client."""
        publisher, mock_redis = _make_publisher()
        await publisher.close()
        mock_redis.aclose.assert_called_once()
