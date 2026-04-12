"""Unit tests for ``api_server.services.livekit_service.LiveKitService``.

Mocks the ``livekit.api`` surface — ``LiveKitAPI``/``RoomService``/
``AccessToken``/``VideoGrants`` — so tests do not require a running
LiveKit server.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from api_server.services.livekit_service import LiveKitService

# ---------------------------------------------------------------------------
# ensure_room
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_room_returns_sid_and_closes_client() -> None:
    """Happy path: create_room returns a Room with .sid; client is closed."""
    svc = LiveKitService(url="ws://lk.test", api_key="k", api_secret="s")

    room_info = MagicMock()
    room_info.sid = "RM_sid_123"

    mock_room_service = MagicMock()
    mock_room_service.create_room = AsyncMock(return_value=room_info)

    mock_lkapi = MagicMock()
    mock_lkapi.room = mock_room_service
    mock_lkapi.aclose = AsyncMock()

    with (
        patch(
            "api_server.services.livekit_service.api.LiveKitAPI",
            return_value=mock_lkapi,
        ) as mock_ctor,
        patch("api_server.services.livekit_service.api.CreateRoomRequest") as mock_req,
    ):
        sid = await svc.ensure_room("meeting-abc")

    assert sid == "RM_sid_123"
    mock_ctor.assert_called_once_with("ws://lk.test", "k", "s")
    mock_req.assert_called_once_with(name="meeting-abc")
    mock_room_service.create_room.assert_awaited_once()
    mock_lkapi.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_room_closes_client_on_error() -> None:
    """If create_room raises, aclose() still runs (finally block)."""
    svc = LiveKitService(url="ws://lk.test", api_key="k", api_secret="s")

    mock_room_service = MagicMock()
    mock_room_service.create_room = AsyncMock(side_effect=RuntimeError("boom"))

    mock_lkapi = MagicMock()
    mock_lkapi.room = mock_room_service
    mock_lkapi.aclose = AsyncMock()

    with (
        patch(
            "api_server.services.livekit_service.api.LiveKitAPI",
            return_value=mock_lkapi,
        ),
        patch("api_server.services.livekit_service.api.CreateRoomRequest"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await svc.ensure_room("meeting-abc")

    mock_lkapi.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# generate_participant_token
# ---------------------------------------------------------------------------


def _make_chained_access_token_mock() -> tuple[MagicMock, MagicMock]:
    """Return (AccessToken ctor mock, instance mock) with all .with_* chained."""
    token_instance = MagicMock()
    token_instance.with_identity.return_value = token_instance
    token_instance.with_name.return_value = token_instance
    token_instance.with_ttl.return_value = token_instance
    token_instance.with_grants.return_value = token_instance
    token_instance.to_jwt.return_value = "signed.jwt.value"

    ctor = MagicMock(return_value=token_instance)
    return ctor, token_instance


def test_generate_participant_token_identity_is_human_prefixed() -> None:
    """Identity must be ``human-<user_id>``."""
    svc = LiveKitService(url="ws://lk.test", api_key="k", api_secret="s")
    user_id = UUID("11111111-2222-3333-4444-555555555555")

    ctor, token_instance = _make_chained_access_token_mock()
    with (
        patch("api_server.services.livekit_service.api.AccessToken", ctor),
        patch("api_server.services.livekit_service.api.VideoGrants") as grants,
    ):
        jwt = svc.generate_participant_token(user_id, "Alice", "room-x")

    assert jwt == "signed.jwt.value"
    ctor.assert_called_once_with("k", "s")
    token_instance.with_identity.assert_called_once_with(
        "human-11111111-2222-3333-4444-555555555555"
    )
    token_instance.with_name.assert_called_once_with("Alice")
    grants.assert_called_once_with(
        room_join=True,
        room="room-x",
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )


def test_generate_participant_token_uses_configured_ttl() -> None:
    """with_ttl is called with a timedelta matching token_ttl_seconds."""
    from datetime import timedelta

    svc = LiveKitService(
        url="ws://lk.test",
        api_key="k",
        api_secret="s",
        token_ttl_seconds=900,
    )
    user_id = UUID("11111111-2222-3333-4444-555555555555")

    ctor, token_instance = _make_chained_access_token_mock()
    with (
        patch("api_server.services.livekit_service.api.AccessToken", ctor),
        patch("api_server.services.livekit_service.api.VideoGrants"),
    ):
        svc.generate_participant_token(user_id, "Alice", "room-x")

    token_instance.with_ttl.assert_called_once_with(timedelta(seconds=900))


def test_generate_participant_token_default_ttl_is_6_hours() -> None:
    """Default TTL is 21600 seconds (6 hours)."""
    from datetime import timedelta

    svc = LiveKitService(url="ws://lk.test", api_key="k", api_secret="s")
    user_id = UUID("11111111-2222-3333-4444-555555555555")

    ctor, token_instance = _make_chained_access_token_mock()
    with (
        patch("api_server.services.livekit_service.api.AccessToken", ctor),
        patch("api_server.services.livekit_service.api.VideoGrants"),
    ):
        svc.generate_participant_token(user_id, "Alice", "room-x")

    token_instance.with_ttl.assert_called_once_with(timedelta(seconds=21600))


# ---------------------------------------------------------------------------
# url property
# ---------------------------------------------------------------------------


def test_url_property_returns_configured_url() -> None:
    svc = LiveKitService(url="ws://lk.test", api_key="k", api_secret="s")
    assert svc.url == "ws://lk.test"
