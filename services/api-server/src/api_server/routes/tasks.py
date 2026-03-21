"""Task CRUD endpoints (wired to database)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth_deps import CurrentUser
from api_server.deps import get_db_session, get_event_publisher
from api_server.event_publisher import EventPublisher
from convene_core.database.models import TaskORM
from convene_core.events.definitions import TaskCreated, TaskUpdated
from convene_core.models.task import Task, TaskPriority, TaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    """Request body for creating a new task.

    Attributes:
        meeting_id: ID of the meeting this task was extracted from.
        description: Human-readable description of the task.
        assignee_id: Optional participant assigned to the task.
        due_date: Optional due date.
        priority: Task priority level.
    """

    meeting_id: UUID
    description: str
    assignee_id: UUID | None = None
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskStatusUpdateRequest(BaseModel):
    """Request body for updating a task's status.

    Attributes:
        status: The new status to transition to.
    """

    status: TaskStatus


class TaskResponse(BaseModel):
    """Response model for a single task.

    Attributes:
        id: Unique task identifier.
        meeting_id: ID of the originating meeting.
        description: Task description.
        assignee_id: Assigned participant ID.
        due_date: Task due date.
        priority: Priority level.
        status: Current task status.
        source_utterance: Original transcript text.
        created_at: Record creation timestamp.
        updated_at: Record last-update timestamp.
    """

    id: UUID
    meeting_id: UUID
    description: str
    assignee_id: UUID | None = None
    due_date: date | None = None
    priority: str
    status: str
    source_utterance: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    """Paginated list of tasks.

    Attributes:
        items: List of task response objects.
        total: Total number of tasks matching the query.
    """

    items: list[TaskResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(task: TaskORM) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        meeting_id=task.meeting_id,
        description=task.description,
        assignee_id=task.assignee_id,
        due_date=task.due_date,
        priority=task.priority,
        status=task.status,
        source_utterance=task.source_utterance,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _orm_to_domain(task: TaskORM) -> Task:
    """Convert a TaskORM row to a domain Task model.

    Args:
        task: The ORM task row with all fields populated.

    Returns:
        A :class:`~convene_core.models.task.Task` domain model.
    """
    dep_ids: list[UUID] = [
        UUID(dep) for dep in (task.dependencies or [])
    ]
    return Task(
        id=task.id,
        meeting_id=task.meeting_id,
        description=task.description,
        assignee_id=task.assignee_id,
        due_date=task.due_date,
        priority=TaskPriority(task.priority),
        status=TaskStatus(task.status),
        dependencies=dep_ids,
        source_utterance=task.source_utterance,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def _safe_publish(publisher: EventPublisher, event: TaskCreated | TaskUpdated) -> None:
    """Publish an event, swallowing errors to avoid breaking the HTTP response.

    Args:
        publisher: The event publisher to use.
        event: The domain event to publish.
    """
    try:
        await publisher.publish(event)
    except Exception:
        logger.exception(
            "Failed to publish %s — continuing without event",
            event.event_type,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    _current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    meeting_id: UUID | None = None,
) -> TaskListResponse:
    """List tasks, optionally filtered by meeting.

    Args:
        _current_user: Authenticated user.
        db: Database session.
        meeting_id: Optional meeting ID filter.

    Returns:
        TaskListResponse with task data.
    """
    query = select(TaskORM)
    count_query = select(func.count()).select_from(TaskORM)

    if meeting_id is not None:
        query = query.where(TaskORM.meeting_id == meeting_id)
        count_query = count_query.where(TaskORM.meeting_id == meeting_id)

    result = await db.execute(query.order_by(TaskORM.created_at.desc()))
    tasks = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return TaskListResponse(
        items=[_to_response(t) for t in tasks],
        total=total,
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreateRequest,
    _current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> TaskResponse:
    """Create a new task and emit a ``task.created`` event.

    Args:
        body: The task creation payload.
        _current_user: Authenticated user.
        db: Database session.
        publisher: Redis event publisher.

    Returns:
        TaskResponse with the newly created task data.
    """
    now = datetime.now(tz=UTC)
    task = TaskORM(
        id=uuid4(),
        meeting_id=body.meeting_id,
        description=body.description,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        priority=body.priority.value,
        status=TaskStatus.PENDING.value,
        dependencies=[],
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()

    domain_task = _orm_to_domain(task)
    await _safe_publish(publisher, TaskCreated(task=domain_task))

    return _to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    _current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskResponse:
    """Get a single task by ID.

    Args:
        task_id: The UUID of the task to retrieve.
        _current_user: Authenticated user.
        db: Database session.

    Returns:
        TaskResponse for the requested task.

    Raises:
        HTTPException: 404 if task not found.
    """
    result = await db.execute(select(TaskORM).where(TaskORM.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return _to_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_status(
    task_id: UUID,
    body: TaskStatusUpdateRequest,
    _current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> TaskResponse:
    """Update the status of an existing task and emit a ``task.updated`` event.

    Args:
        task_id: The UUID of the task to update.
        body: The status update payload.
        _current_user: Authenticated user.
        db: Database session.
        publisher: Redis event publisher.

    Returns:
        TaskResponse reflecting the updated status.

    Raises:
        HTTPException: 404 if task not found.
    """
    result = await db.execute(select(TaskORM).where(TaskORM.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    previous_status = TaskStatus(task.status)
    task.status = body.status.value
    task.updated_at = datetime.now(tz=UTC)
    await db.flush()

    domain_task = _orm_to_domain(task)
    await _safe_publish(
        publisher,
        TaskUpdated(task=domain_task, previous_status=previous_status),
    )

    return _to_response(task)
