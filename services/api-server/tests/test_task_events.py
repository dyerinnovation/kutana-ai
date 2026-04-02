"""Unit tests for task event emission in API routes.

Tests verify that task.created and task.updated events are published when
tasks are created or updated via the REST API.  All external dependencies
(database, Redis) are mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api_server.event_publisher import EventPublisher

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_publisher() -> tuple[EventPublisher, AsyncMock]:
    """Build an EventPublisher backed by a mock Redis client.

    Returns:
        Tuple of (publisher, mock_redis).
    """
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="9999999999-0")
    publisher = EventPublisher(redis_client=mock_redis)
    return publisher, mock_redis


def _make_task_orm(
    task_id: object | None = None,
    meeting_id: object | None = None,
    status: str = "pending",
    priority: str = "medium",
) -> MagicMock:
    """Create a minimal TaskORM mock."""
    mock_task = MagicMock()
    mock_task.id = task_id or uuid4()
    mock_task.meeting_id = meeting_id or uuid4()
    mock_task.description = "Test task description"
    mock_task.assignee_id = None
    mock_task.due_date = None
    mock_task.priority = priority
    mock_task.status = status
    mock_task.source_utterance = None
    mock_task.dependencies = []
    mock_task.created_at = datetime.now(tz=UTC)
    mock_task.updated_at = datetime.now(tz=UTC)
    return mock_task


# ---------------------------------------------------------------------------
# EventPublisher — api-server variant
# ---------------------------------------------------------------------------


class TestApiServerEventPublisher:
    """Tests for api_server.event_publisher.EventPublisher."""

    async def test_publish_calls_xadd_with_stream_key(self) -> None:
        """publish() calls xadd on the injected Redis client."""
        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_redis_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Test event",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        await publisher.publish(event)

        mock_redis.xadd.assert_called_once()
        from api_server.event_publisher import STREAM_KEY
        assert mock_redis.xadd.call_args[0][0] == STREAM_KEY

    async def test_publish_sets_event_type_field(self) -> None:
        """Stream entry contains the correct event_type field."""
        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_redis_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Check email",
            priority=TaskPriority.LOW,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        await publisher.publish(event)

        fields = mock_redis.xadd.call_args[0][1]
        assert fields["event_type"] == "task.created"

    async def test_publish_task_updated_event_type(self) -> None:
        """task.updated events are correctly named in the stream."""
        from kutana_core.events.definitions import TaskUpdated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_redis_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Finish proposal",
            priority=TaskPriority.HIGH,
            status=TaskStatus.DONE,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskUpdated(task=task, previous_status=TaskStatus.IN_PROGRESS)

        await publisher.publish(event)

        fields = mock_redis.xadd.call_args[0][1]
        assert fields["event_type"] == "task.updated"

    async def test_publish_returns_entry_id(self) -> None:
        """publish() returns the entry ID from xadd."""
        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus

        publisher, mock_redis = _make_redis_publisher()
        mock_redis.xadd.return_value = "1111111111-0"

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Update readme",
            priority=TaskPriority.LOW,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        entry_id = await publisher.publish(event)
        assert entry_id == "1111111111-0"


# ---------------------------------------------------------------------------
# _orm_to_domain helper
# ---------------------------------------------------------------------------


class TestOrmToDomain:
    """Tests for the _orm_to_domain helper in tasks route."""

    def test_converts_all_fields(self) -> None:
        """_orm_to_domain maps all ORM fields to the domain model."""
        from api_server.routes.tasks import _orm_to_domain
        from kutana_core.models.task import TaskPriority, TaskStatus

        dep_id = uuid4()
        task_orm = _make_task_orm(status="in_progress", priority="high")
        task_orm.dependencies = [str(dep_id)]

        domain_task = _orm_to_domain(task_orm)

        assert domain_task.id == task_orm.id
        assert domain_task.meeting_id == task_orm.meeting_id
        assert domain_task.description == task_orm.description
        assert domain_task.status == TaskStatus.IN_PROGRESS
        assert domain_task.priority == TaskPriority.HIGH
        assert domain_task.dependencies == [dep_id]

    def test_empty_dependencies_list(self) -> None:
        """_orm_to_domain handles empty dependencies correctly."""
        from api_server.routes.tasks import _orm_to_domain

        task_orm = _make_task_orm()
        task_orm.dependencies = []

        domain_task = _orm_to_domain(task_orm)
        assert domain_task.dependencies == []

    def test_none_dependencies_treated_as_empty(self) -> None:
        """_orm_to_domain handles None dependencies without raising."""
        from api_server.routes.tasks import _orm_to_domain

        task_orm = _make_task_orm()
        task_orm.dependencies = None

        domain_task = _orm_to_domain(task_orm)
        assert domain_task.dependencies == []


# ---------------------------------------------------------------------------
# _safe_publish helper
# ---------------------------------------------------------------------------


class TestSafePublish:
    """Tests for the _safe_publish helper in tasks route."""

    async def test_publish_error_is_swallowed(self) -> None:
        """_safe_publish does not re-raise exceptions from the publisher."""
        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus
        from api_server.routes.tasks import _safe_publish

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(side_effect=RuntimeError("Redis is down"))
        publisher = EventPublisher(redis_client=mock_redis)

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Run integration tests",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        # Should not raise
        await _safe_publish(publisher, event)

    async def test_publish_success_calls_publisher(self) -> None:
        """_safe_publish delegates to the publisher when no error occurs."""
        from kutana_core.events.definitions import TaskCreated
        from kutana_core.models.task import Task, TaskPriority, TaskStatus
        from api_server.routes.tasks import _safe_publish

        publisher, mock_redis = _make_redis_publisher()

        task = Task(
            id=uuid4(),
            meeting_id=uuid4(),
            description="Ship the feature",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        event = TaskCreated(task=task)

        await _safe_publish(publisher, event)

        mock_redis.xadd.assert_called_once()
