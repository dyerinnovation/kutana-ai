"""Unit tests for TaskExtractor ORM persistence and event emission.

All tests use mocked LLM providers, database sessions, and event publishers —
no live database, LLM calls, or Redis connections are made.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from convene_core.database.models import TaskORM
from convene_core.models.task import Task, TaskPriority, TaskStatus
from convene_core.models.transcript import TranscriptSegment
from task_engine.extractor import TaskExtractor

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(meeting_id: UUID | None = None) -> TranscriptSegment:
    """Create a minimal TranscriptSegment for testing."""
    return TranscriptSegment(
        meeting_id=meeting_id or uuid4(),
        speaker_id="spk_0",
        text="Alice will send the report by Friday.",
        start_time=0.0,
        end_time=5.0,
        confidence=0.95,
    )


def _make_task(
    meeting_id: UUID | None = None,
    description: str = "Send the report by Friday",
    priority: TaskPriority = TaskPriority.MEDIUM,
    assignee_id: UUID | None = None,
    due_date: date | None = None,
    source_utterance: str | None = "Alice will send the report by Friday.",
) -> Task:
    """Create a minimal Task domain model for testing."""
    return Task(
        id=uuid4(),
        meeting_id=meeting_id or uuid4(),
        description=description,
        assignee_id=assignee_id,
        due_date=due_date,
        priority=priority,
        status=TaskStatus.PENDING,
        dependencies=[],
        source_utterance=source_utterance,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _make_extractor(
    extracted_tasks: list[Task] | None = None,
    event_publisher: AsyncMock | None = None,
) -> tuple[TaskExtractor, AsyncMock, MagicMock]:
    """Build a TaskExtractor with a mocked LLM and session factory.

    Args:
        extracted_tasks: Tasks the mock LLM will return.
        event_publisher: Optional mock EventPublisher.

    Returns:
        Tuple of (extractor, mock_session, mock_session_factory).
    """
    mock_llm = AsyncMock()
    mock_llm.extract_tasks.return_value = extracted_tasks or []

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    extractor = TaskExtractor(
        llm_provider=mock_llm,
        session_factory=mock_factory,
        event_publisher=event_publisher,
    )
    return extractor, mock_session, mock_factory


# ---------------------------------------------------------------------------
# extract_from_segments — no segments
# ---------------------------------------------------------------------------


class TestExtractFromSegmentsEmpty:
    """Tests for extract_from_segments with empty input."""

    async def test_returns_empty_list_when_no_segments(self) -> None:
        """Passing an empty list returns [] and skips LLM call."""
        extractor, _mock_session, _ = _make_extractor()
        result = await extractor.extract_from_segments([], context="")
        assert result == []
        extractor._llm.extract_tasks.assert_not_called()

    async def test_no_db_write_when_no_segments(self) -> None:
        """No session is opened when segments list is empty."""
        extractor, _mock_session, mock_factory = _make_extractor()
        await extractor.extract_from_segments([], context="")
        mock_factory.assert_not_called()


# ---------------------------------------------------------------------------
# extract_from_segments — LLM returns no tasks
# ---------------------------------------------------------------------------


class TestExtractFromSegmentsNoTasks:
    """Tests for extract_from_segments when LLM finds nothing."""

    async def test_returns_empty_list_when_llm_returns_nothing(self) -> None:
        """LLM returning [] propagates to the caller."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        extractor, _mock_session, _mock_factory = _make_extractor(extracted_tasks=[])

        result = await extractor.extract_from_segments([segment], context="")
        assert result == []

    async def test_no_db_write_when_llm_returns_nothing(self) -> None:
        """No database write when LLM returns no tasks."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        extractor, _mock_session, mock_factory = _make_extractor(extracted_tasks=[])

        await extractor.extract_from_segments([segment], context="")
        mock_factory.assert_not_called()


# ---------------------------------------------------------------------------
# extract_from_segments — happy path
# ---------------------------------------------------------------------------


class TestExtractFromSegmentsHappyPath:
    """Tests for the full extraction + persistence happy path."""

    async def test_returns_extracted_tasks(self) -> None:
        """Tasks returned by the LLM are returned to the caller."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)
        extractor, _mock_session, _ = _make_extractor(extracted_tasks=[task])

        result = await extractor.extract_from_segments([segment], context="ctx")
        assert result == [task]

    async def test_llm_called_with_segments_and_context(self) -> None:
        """LLM provider receives the correct segments and context."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)
        extractor, _, _ = _make_extractor(extracted_tasks=[task])

        await extractor.extract_from_segments([segment], context="some context")
        extractor._llm.extract_tasks.assert_called_once_with([segment], "some context")

    async def test_orm_task_added_to_session(self) -> None:
        """TaskORM object is added to the session for each extracted task."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)
        extractor, mock_session, _ = _make_extractor(extracted_tasks=[task])

        await extractor.extract_from_segments([segment], context="")

        assert mock_session.add.call_count == 1
        added_obj = mock_session.add.call_args[0][0]
        assert isinstance(added_obj, TaskORM)

    async def test_orm_task_fields_match_domain_task(self) -> None:
        """Fields on the persisted TaskORM match the domain Task."""
        dep_id = uuid4()
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id, description="Write tests")
        task = task.model_copy(update={"dependencies": [dep_id]})

        extractor, mock_session, _ = _make_extractor(extracted_tasks=[task])
        await extractor.extract_from_segments([segment], context="")

        orm_task: TaskORM = mock_session.add.call_args[0][0]
        assert orm_task.id == task.id
        assert orm_task.meeting_id == task.meeting_id
        assert orm_task.description == task.description
        assert orm_task.priority == str(task.priority)
        assert orm_task.status == str(task.status)
        assert orm_task.dependencies == [str(dep_id)]

    async def test_multiple_tasks_all_added(self) -> None:
        """Multiple extracted tasks are all added in a single session."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        tasks = [_make_task(meeting_id=meeting_id, description=f"Task {i}") for i in range(3)]
        extractor, mock_session, _ = _make_extractor(extracted_tasks=tasks)

        result = await extractor.extract_from_segments([segment], context="")
        assert len(result) == 3
        assert mock_session.add.call_count == 3

    async def test_session_committed_after_persist(self) -> None:
        """Session.commit() is called exactly once after adding all tasks."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)
        extractor, mock_session, _ = _make_extractor(extracted_tasks=[task])

        await extractor.extract_from_segments([segment], context="")
        mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# _persist_tasks — error handling
# ---------------------------------------------------------------------------


class TestPersistTasksErrorHandling:
    """Tests for error handling in _persist_tasks."""

    async def test_rollback_on_commit_failure(self) -> None:
        """Session is rolled back if commit raises."""
        meeting_id = uuid4()
        task = _make_task(meeting_id=meeting_id)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit.side_effect = RuntimeError("DB is down")

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        mock_llm = AsyncMock()
        extractor = TaskExtractor(llm_provider=mock_llm, session_factory=mock_factory)

        with pytest.raises(RuntimeError, match="DB is down"):
            await extractor._persist_tasks([task])

        mock_session.rollback.assert_called_once()

    async def test_rollback_on_add_failure(self) -> None:
        """Session is rolled back if session.add() raises."""
        meeting_id = uuid4()
        task = _make_task(meeting_id=meeting_id)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.add.side_effect = ValueError("Invalid data")

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        mock_llm = AsyncMock()
        extractor = TaskExtractor(llm_provider=mock_llm, session_factory=mock_factory)

        with pytest.raises(ValueError, match="Invalid data"):
            await extractor._persist_tasks([task])

        mock_session.rollback.assert_called_once()

    async def test_empty_task_list_does_not_open_session(self) -> None:
        """_persist_tasks with an empty list still opens a session and commits."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        mock_llm = AsyncMock()
        extractor = TaskExtractor(llm_provider=mock_llm, session_factory=mock_factory)

        # Calling _persist_tasks with empty list still commits (no-op batch)
        await extractor._persist_tasks([])
        mock_session.add.assert_not_called()
        mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Event emission — task.created
# ---------------------------------------------------------------------------


class TestEventEmission:
    """Tests for task.created event emission after extraction."""

    async def test_no_events_when_no_publisher(self) -> None:
        """No events are emitted when event_publisher is None."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)
        extractor, _mock_session, _ = _make_extractor(extracted_tasks=[task])

        # Should complete without errors even with no publisher
        result = await extractor.extract_from_segments([segment], context="")
        assert result == [task]

    async def test_event_published_for_each_task(self) -> None:
        """One task.created event is published per extracted task."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        tasks = [_make_task(meeting_id=meeting_id, description=f"Task {i}") for i in range(3)]

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(return_value="1234-0")

        extractor, _mock_session, _ = _make_extractor(
            extracted_tasks=tasks,
            event_publisher=mock_publisher,
        )

        await extractor.extract_from_segments([segment], context="")

        assert mock_publisher.publish.call_count == 3

    async def test_event_type_is_task_created(self) -> None:
        """Published event has event_type 'task.created'."""
        from convene_core.events.definitions import TaskCreated

        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(return_value="1234-0")

        extractor, _, _ = _make_extractor(
            extracted_tasks=[task],
            event_publisher=mock_publisher,
        )

        await extractor.extract_from_segments([segment], context="")

        published_event = mock_publisher.publish.call_args[0][0]
        assert isinstance(published_event, TaskCreated)
        assert published_event.task == task

    async def test_no_events_when_llm_returns_nothing(self) -> None:
        """No events are emitted when LLM finds no tasks."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(return_value="1234-0")

        extractor, _, _ = _make_extractor(
            extracted_tasks=[],
            event_publisher=mock_publisher,
        )

        await extractor.extract_from_segments([segment], context="")

        mock_publisher.publish.assert_not_called()

    async def test_no_events_when_no_segments(self) -> None:
        """No events are emitted when segments list is empty."""
        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(return_value="1234-0")

        extractor, _, _ = _make_extractor(
            extracted_tasks=[],
            event_publisher=mock_publisher,
        )

        await extractor.extract_from_segments([], context="")

        mock_publisher.publish.assert_not_called()

    async def test_publish_error_does_not_raise(self) -> None:
        """A publish failure is swallowed — extraction still returns tasks."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(side_effect=RuntimeError("Redis down"))

        extractor, _, _ = _make_extractor(
            extracted_tasks=[task],
            event_publisher=mock_publisher,
        )

        # Should not raise despite publish failure
        result = await extractor.extract_from_segments([segment], context="")
        assert result == [task]

    async def test_publish_called_after_persist(self) -> None:
        """Events are only emitted after the database commit succeeds."""
        meeting_id = uuid4()
        segment = _make_segment(meeting_id)
        task = _make_task(meeting_id=meeting_id)

        call_order: list[str] = []

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        async def _tracked_commit() -> None:
            call_order.append("commit")

        mock_session.commit = AsyncMock(side_effect=_tracked_commit)

        mock_factory = MagicMock()
        mock_factory.return_value = mock_session

        mock_llm = AsyncMock()
        mock_llm.extract_tasks.return_value = [task]

        async def _tracked_publish(event: object) -> str:
            call_order.append("publish")
            return "1234-0"

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(side_effect=_tracked_publish)

        extractor = TaskExtractor(
            llm_provider=mock_llm,
            session_factory=mock_factory,
            event_publisher=mock_publisher,
        )

        await extractor.extract_from_segments([segment], context="")

        assert call_order == ["commit", "publish"]
