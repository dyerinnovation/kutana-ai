"""Task domain model with status transition validation."""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskPriority(enum.StrEnum):
    """Priority level of a task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(enum.StrEnum):
    """Status of a task with defined transition rules."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED},
    TaskStatus.IN_PROGRESS: {TaskStatus.DONE, TaskStatus.BLOCKED},
    TaskStatus.BLOCKED: {TaskStatus.PENDING, TaskStatus.IN_PROGRESS},
    TaskStatus.DONE: set(),
}


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class Task(BaseModel):
    """Represents an action item extracted from a meeting.

    Attributes:
        id: Unique task identifier.
        meeting_id: ID of the meeting this task was extracted from.
        description: Human-readable description of the task.
        assignee_id: ID of the participant assigned to this task.
        due_date: Optional due date for the task.
        priority: Priority level of the task.
        status: Current status of the task.
        dependencies: List of task IDs this task depends on.
        source_utterance: Original transcript text that generated this task.
        created_at: When this record was created.
        updated_at: When this record was last updated.
    """

    id: UUID = Field(default_factory=uuid4)
    meeting_id: UUID
    description: str
    assignee_id: UUID | None = None
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[UUID] = Field(default_factory=list)
    source_utterance: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @classmethod
    def validate_transition(cls, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """Check whether a status transition is valid.

        Args:
            from_status: The current status of the task.
            to_status: The desired new status.

        Returns:
            True if the transition is allowed, False otherwise.
        """
        return to_status in VALID_TRANSITIONS.get(from_status, set())
