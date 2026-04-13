"""Unit tests for DELETE /v1/meetings/{id}.

The route is exercised as a coroutine with a mocked ``AsyncSession``. We
only verify authorization, not-found behavior, and that cascading deletes
are issued before the meeting row is removed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api_server.routes.meetings import delete_meeting

pytestmark = pytest.mark.asyncio


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    return user


def _make_meeting(meeting_id=None, owner_id=None) -> MagicMock:
    meeting = MagicMock()
    meeting.id = meeting_id or uuid4()
    meeting.owner_id = owner_id
    meeting.platform = "kutana"
    meeting.title = "Test"
    meeting.scheduled_at = datetime.now(tz=UTC)
    meeting.started_at = None
    meeting.ended_at = None
    meeting.status = "scheduled"
    meeting.created_at = datetime.now(tz=UTC)
    meeting.updated_at = datetime.now(tz=UTC)
    return meeting


def _mock_db(meeting: MagicMock | None) -> MagicMock:
    db = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=meeting)
    db.execute = AsyncMock(return_value=scalar_result)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    return db


async def test_delete_meeting_404_when_missing() -> None:
    user = _make_user()
    db = _mock_db(meeting=None)
    with pytest.raises(HTTPException) as exc:
        await delete_meeting(uuid4(), user, db)
    assert exc.value.status_code == 404


async def test_delete_meeting_403_when_not_owner() -> None:
    user = _make_user()
    other = uuid4()
    meeting = _make_meeting(owner_id=other)
    db = _mock_db(meeting=meeting)
    with pytest.raises(HTTPException) as exc:
        await delete_meeting(meeting.id, user, db)
    assert exc.value.status_code == 403


async def test_delete_meeting_cascades_and_removes_row() -> None:
    user = _make_user()
    meeting = _make_meeting(owner_id=user.id)
    db = _mock_db(meeting=meeting)

    result = await delete_meeting(meeting.id, user, db)

    assert result is None
    # 1 initial select + 10 cascade deletes
    assert db.execute.await_count == 11
    db.delete.assert_awaited_once_with(meeting)
    db.flush.assert_awaited()


async def test_delete_meeting_allows_legacy_unowned() -> None:
    user = _make_user()
    meeting = _make_meeting(owner_id=None)
    db = _mock_db(meeting=meeting)

    await delete_meeting(meeting.id, user, db)
    db.delete.assert_awaited_once_with(meeting)


_ = SimpleNamespace
