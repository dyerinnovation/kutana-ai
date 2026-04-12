"""Unit tests for LiveKit room provisioning and token issuance in meetings routes.

Both ``start_meeting`` and ``issue_livekit_token`` are exercised directly as
coroutines with fully-mocked dependencies (database, event publisher,
``LiveKitService``). No real LiveKit server or PostgreSQL is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api_server.routes import meetings as meetings_module
from api_server.routes.meetings import (
    LiveKitTokenResponse,
    issue_livekit_token,
    start_meeting,
)
from kutana_core.models.meeting import MeetingStatus

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.name = "Test User"
    user.email = "test@example.com"
    return user


def _make_meeting(meeting_id=None, owner_id=None, status_val: str = "scheduled") -> MagicMock:
    meeting = MagicMock()
    meeting.id = meeting_id or uuid4()
    meeting.owner_id = owner_id
    meeting.platform = "kutana"
    meeting.title = "Test Meeting"
    meeting.scheduled_at = datetime.now(tz=UTC)
    meeting.started_at = None
    meeting.ended_at = None
    meeting.status = status_val
    meeting.created_at = datetime.now(tz=UTC)
    meeting.updated_at = datetime.now(tz=UTC)
    return meeting


def _make_room(meeting_id, name: str = "meeting-xyz", livekit_room_id=None) -> MagicMock:
    room = MagicMock()
    room.id = uuid4()
    room.meeting_id = meeting_id
    room.name = name
    room.livekit_room_id = livekit_room_id
    room.status = "active"
    return room


def _scalar_one_or_none_result(value):
    """Return a mock SQLAlchemy result whose scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    # scalars().all() for selection lookups
    scalars = MagicMock()
    scalars.all.return_value = []
    result.scalars.return_value = scalars
    return result


def _make_db_execute(return_values: list):
    """Build an AsyncMock db.execute that returns each value in turn."""
    results = [
        _scalar_one_or_none_result(v) if not isinstance(v, MagicMock) else v for v in return_values
    ]
    execute = AsyncMock(side_effect=results)
    return execute


def _make_settings(livekit_url: str = "wss://lk.test") -> SimpleNamespace:
    return SimpleNamespace(
        livekit_url=livekit_url,
        livekit_api_key="key",
        livekit_api_secret="secret",
        livekit_token_ttl_seconds=21600,
        database_url="postgresql+asyncpg://x",
        debug=False,
    )


# ---------------------------------------------------------------------------
# start_meeting — LiveKit room provisioning
# ---------------------------------------------------------------------------


class TestStartMeetingLiveKit:
    async def test_persists_livekit_room_id_after_ensure_room(self) -> None:
        """When livekit_url is set, ensure_room is called and sid is stored."""
        user = _make_user()
        meeting_id = uuid4()
        meeting = _make_meeting(meeting_id=meeting_id, owner_id=user.id)

        # DB execute sequence:
        # 1. initial meeting lookup
        # 2. room lookup (returns None -> we create)
        # 3. selections lookup (empty)
        meeting_result = _scalar_one_or_none_result(meeting)
        room_result = _scalar_one_or_none_result(None)
        selections_result = _scalar_one_or_none_result(None)
        db = MagicMock()
        db.execute = AsyncMock(side_effect=[meeting_result, room_result, selections_result])
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.commit = AsyncMock()

        publisher = MagicMock()
        publisher.publish = AsyncMock()

        lk = MagicMock()
        lk.ensure_room = AsyncMock(return_value="RM_abc123")

        settings = _make_settings(livekit_url="wss://lk.test")

        with patch.object(meetings_module, "_build_session_factory", MagicMock()):
            await start_meeting(
                meeting_id=meeting_id,
                current_user=user,
                db=db,
                publisher=publisher,
                settings=settings,
                lk=lk,
            )

        lk.ensure_room.assert_awaited_once()
        # Last positional/kw arg should be the room name we created:
        room_name_arg = lk.ensure_room.await_args.args[0]
        assert room_name_arg == f"meeting-{meeting_id}"

        # The RoomORM added to db should have its livekit_room_id set
        added_room = db.add.call_args_list[0].args[0]
        assert added_room.livekit_room_id == "RM_abc123"
        assert added_room.meeting_id == meeting_id

    async def test_skips_livekit_when_url_empty(self) -> None:
        """With empty livekit_url, no ensure_room call and no room row added."""
        user = _make_user()
        meeting_id = uuid4()
        meeting = _make_meeting(meeting_id=meeting_id, owner_id=user.id)

        # Only two executes: meeting lookup + selections lookup (no room lookup)
        db = MagicMock()
        db.execute = AsyncMock(
            side_effect=[
                _scalar_one_or_none_result(meeting),
                _scalar_one_or_none_result(None),
            ]
        )
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        db.commit = AsyncMock()

        publisher = MagicMock()
        publisher.publish = AsyncMock()

        lk = MagicMock()
        lk.ensure_room = AsyncMock()

        settings = _make_settings(livekit_url="")

        with patch.object(meetings_module, "_build_session_factory", MagicMock()):
            await start_meeting(
                meeting_id=meeting_id,
                current_user=user,
                db=db,
                publisher=publisher,
                settings=settings,
                lk=lk,
            )

        lk.ensure_room.assert_not_called()
        db.add.assert_not_called()


# ---------------------------------------------------------------------------
# issue_livekit_token
# ---------------------------------------------------------------------------


class TestIssueLiveKitToken:
    async def test_returns_token_url_room_name(self) -> None:
        """Happy path: accessible meeting + provisioned room returns 200."""
        user = _make_user()
        meeting_id = uuid4()
        meeting = _make_meeting(meeting_id=meeting_id, owner_id=user.id)
        room = _make_room(meeting_id=meeting_id, name="meeting-xyz", livekit_room_id="RM_abc")

        db = MagicMock()
        # _assert_meeting_accessible -> 1 execute (meeting). room lookup -> 1 execute.
        db.execute = AsyncMock(
            side_effect=[
                _scalar_one_or_none_result(meeting),
                _scalar_one_or_none_result(room),
            ]
        )

        lk = MagicMock()
        lk.generate_participant_token = MagicMock(return_value="jwt.token.here")

        settings = _make_settings(livekit_url="wss://lk.test")

        result = await issue_livekit_token(
            meeting_id=meeting_id,
            current_user=user,
            db=db,
            settings=settings,
            lk=lk,
        )

        assert isinstance(result, LiveKitTokenResponse)
        assert result.token == "jwt.token.here"
        assert result.url == "wss://lk.test"
        assert result.room_name == "meeting-xyz"
        lk.generate_participant_token.assert_called_once_with(
            user_id=user.id,
            user_name="Test User",
            room_name="meeting-xyz",
        )

    async def test_returns_404_when_user_not_on_meeting(self) -> None:
        """_assert_meeting_accessible raises 404 when user can't see meeting."""
        user = _make_user()
        meeting_id = uuid4()

        db = MagicMock()
        # meeting lookup yields None -> not accessible
        db.execute = AsyncMock(side_effect=[_scalar_one_or_none_result(None)])

        lk = MagicMock()
        settings = _make_settings(livekit_url="wss://lk.test")

        with pytest.raises(HTTPException) as excinfo:
            await issue_livekit_token(
                meeting_id=meeting_id,
                current_user=user,
                db=db,
                settings=settings,
                lk=lk,
            )
        # Access-control path returns 404 (not 403) — meeting is "not found"
        # from the caller's perspective. This still enforces authorization.
        assert excinfo.value.status_code == 404

    async def test_returns_409_when_no_room_for_meeting(self) -> None:
        user = _make_user()
        meeting_id = uuid4()
        meeting = _make_meeting(meeting_id=meeting_id, owner_id=user.id)

        db = MagicMock()
        db.execute = AsyncMock(
            side_effect=[
                _scalar_one_or_none_result(meeting),
                _scalar_one_or_none_result(None),  # no room
            ]
        )

        lk = MagicMock()
        settings = _make_settings(livekit_url="wss://lk.test")

        with pytest.raises(HTTPException) as excinfo:
            await issue_livekit_token(
                meeting_id=meeting_id,
                current_user=user,
                db=db,
                settings=settings,
                lk=lk,
            )
        assert excinfo.value.status_code == 409


# Sanity: MeetingStatus constant import stays stable (guards against enum rename).
def test_meeting_status_scheduled_value() -> None:
    assert MeetingStatus.SCHEDULED.value == "scheduled"
