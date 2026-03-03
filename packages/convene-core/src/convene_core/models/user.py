"""User domain model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class User(BaseModel):
    """Domain model for a Convene AI user.

    Attributes:
        id: Unique user identifier.
        email: User email address.
        name: Display name.
        is_active: Whether the account is active.
        created_at: When this record was created.
        updated_at: When this record was last updated.
    """

    id: UUID = Field(default_factory=uuid4)
    email: str
    name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
