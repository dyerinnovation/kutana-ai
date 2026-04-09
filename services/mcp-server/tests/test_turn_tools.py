"""Unit tests for Turn Management MCP tools.

Tests each of the turn management tools by mocking the RedisTurnManager
and MCPIdentity globals in mcp_server.main.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import mcp_server.main as main_module
import pytest
from mcp_server.auth import MCPIdentity
from mcp_server.main import (
    kutana_cancel_hand_raise,
    kutana_get_queue_status,
    kutana_get_speaking_status,
    kutana_mark_finished_speaking,
    kutana_raise_hand,
    kutana_start_speaking,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_AGENT_CONFIG_ID = uuid4()
TEST_MEETING_ID = uuid4()
TEST_HAND_RAISE_ID = uuid4()
TEST_PARTICIPANT_A = uuid4()
TEST_PARTICIPANT_B = uuid4()

TEST_IDENTITY = MCPIdentity(
    user_id=TEST_USER_ID,
    agent_config_id=TEST_AGENT_CONFIG_ID,
    scopes=["meetings:write"],
)

_RAISED_AT = datetime(2026, 3, 23, 12, 0, 0, tzinfo=UTC)
_STARTED_AT = datetime(2026, 3, 23, 12, 5, 0, tzinfo=UTC)


def _make_raise_hand_result(
    queue_position: int = 1,
    hand_raise_id: UUID | None = None,
    was_promoted: bool = False,
) -> MagicMock:
    result = MagicMock()
    result.queue_position = queue_position
    result.hand_raise_id = hand_raise_id or TEST_HAND_RAISE_ID
    result.was_promoted = was_promoted
    return result


def _make_queue_entry(
    participant_id: UUID,
    position: int,
    priority: str = "normal",
    topic: str | None = None,
) -> MagicMock:
    entry = MagicMock()
    entry.participant_id = participant_id
    entry.position = position
    entry.priority = MagicMock()
    entry.priority.value = priority
    entry.topic = topic
    entry.raised_at = _RAISED_AT
    return entry


def _make_queue_status(
    active_speaker_id: UUID | None = None,
    queue: list[MagicMock] | None = None,
) -> MagicMock:
    status = MagicMock()
    status.active_speaker_id = active_speaker_id
    status.queue = queue or []
    return status


def _make_speaking_status(
    is_speaking: bool = False,
    in_queue: bool = False,
    queue_position: int | None = None,
    hand_raise_id: UUID | None = None,
) -> MagicMock:
    status = MagicMock()
    status.is_speaking = is_speaking
    status.in_queue = in_queue
    status.queue_position = queue_position
    status.hand_raise_id = hand_raise_id
    return status


def _make_turn_manager() -> MagicMock:
    """Return a fully mocked TurnManager."""
    tm = MagicMock()
    tm.raise_hand = AsyncMock()
    tm.get_queue_status = AsyncMock()
    tm.get_speaking_status = AsyncMock()
    tm.mark_finished_speaking = AsyncMock()
    tm.cancel_hand_raise = AsyncMock()
    tm.get_active_speaker = AsyncMock()
    tm.start_speaking = AsyncMock()
    return tm


# ---------------------------------------------------------------------------
# kutana_raise_hand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raise_hand_queued() -> None:
    """Raising hand when someone is already speaking returns queue position."""
    tm = _make_turn_manager()
    tm.raise_hand.return_value = _make_raise_hand_result(queue_position=1, was_promoted=False)
    tm.get_active_speaker.return_value = TEST_PARTICIPANT_A

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_raise_hand(str(TEST_MEETING_ID)))

    assert result["queue_position"] == 1
    assert result["hand_raise_id"] == str(TEST_HAND_RAISE_ID)
    assert result["current_speaker"] == str(TEST_PARTICIPANT_A)
    assert result["estimated_wait"] is None

    tm.raise_hand.assert_awaited_once_with(
        TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, priority="normal", topic=None
    )


@pytest.mark.asyncio
async def test_raise_hand_promoted_immediately() -> None:
    """Raising hand when queue is empty promotes to active speaker."""
    tm = _make_turn_manager()
    tm.raise_hand.return_value = _make_raise_hand_result(queue_position=0, was_promoted=True)
    tm.get_active_speaker.return_value = TEST_AGENT_CONFIG_ID

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_raise_hand(str(TEST_MEETING_ID)))

    assert result["queue_position"] == 0
    assert result["current_speaker"] == str(TEST_AGENT_CONFIG_ID)


@pytest.mark.asyncio
async def test_raise_hand_urgent_with_topic() -> None:
    """kutana_raise_hand passes priority and topic through to TurnManager."""
    tm = _make_turn_manager()
    tm.raise_hand.return_value = _make_raise_hand_result(queue_position=1)
    tm.get_active_speaker.return_value = None

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await kutana_raise_hand(str(TEST_MEETING_ID), priority="urgent", topic="Budget update")

    tm.raise_hand.assert_awaited_once_with(
        TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, priority="urgent", topic="Budget update"
    )


# ---------------------------------------------------------------------------
# kutana_get_queue_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_queue_status_with_entries() -> None:
    """kutana_get_queue_status returns ordered queue and your_position."""
    tm = _make_turn_manager()
    entry_a = _make_queue_entry(TEST_PARTICIPANT_A, position=1, topic="Agenda")
    entry_me = _make_queue_entry(TEST_AGENT_CONFIG_ID, position=2)
    tm.get_queue_status.return_value = _make_queue_status(
        active_speaker_id=TEST_PARTICIPANT_B,
        queue=[entry_a, entry_me],
    )

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_get_queue_status(str(TEST_MEETING_ID)))

    assert result["current_speaker"] == str(TEST_PARTICIPANT_B)
    assert result["total_in_queue"] == 2
    assert result["your_position"] == 2
    assert result["queue"][0]["position"] == 1
    assert result["queue"][0]["participant_id"] == str(TEST_PARTICIPANT_A)
    assert result["queue"][0]["topic"] == "Agenda"
    assert result["queue"][1]["position"] == 2


@pytest.mark.asyncio
async def test_get_queue_status_empty() -> None:
    """kutana_get_queue_status with empty queue returns nulls."""
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_get_queue_status(str(TEST_MEETING_ID)))

    assert result["current_speaker"] is None
    assert result["total_in_queue"] == 0
    assert result["your_position"] is None
    assert result["queue"] == []


@pytest.mark.asyncio
async def test_get_queue_status_not_in_queue() -> None:
    """your_position is null when agent is not in the queue."""
    tm = _make_turn_manager()
    entry_other = _make_queue_entry(TEST_PARTICIPANT_A, position=1)
    tm.get_queue_status.return_value = _make_queue_status(queue=[entry_other])

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_get_queue_status(str(TEST_MEETING_ID)))

    assert result["your_position"] is None
    assert result["total_in_queue"] == 1


# ---------------------------------------------------------------------------
# kutana_mark_finished_speaking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_finished_speaking_with_next() -> None:
    """kutana_mark_finished_speaking returns next_speaker when queue has entries."""
    tm = _make_turn_manager()
    tm.mark_finished_speaking.return_value = TEST_PARTICIPANT_A
    entry = _make_queue_entry(TEST_PARTICIPANT_A, position=1)
    tm.get_queue_status.return_value = _make_queue_status(
        active_speaker_id=TEST_PARTICIPANT_A, queue=[entry]
    )

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_mark_finished_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "finished"
    assert result["next_speaker"] == str(TEST_PARTICIPANT_A)
    assert result["queue_remaining"] == 1

    tm.mark_finished_speaking.assert_awaited_once_with(TEST_MEETING_ID, TEST_AGENT_CONFIG_ID)


@pytest.mark.asyncio
async def test_mark_finished_speaking_empty_queue() -> None:
    """kutana_mark_finished_speaking returns null next_speaker when queue empties."""
    tm = _make_turn_manager()
    tm.mark_finished_speaking.return_value = None
    tm.get_queue_status.return_value = _make_queue_status()

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_mark_finished_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "finished"
    assert result["next_speaker"] is None
    assert result["queue_remaining"] == 0


# ---------------------------------------------------------------------------
# kutana_cancel_hand_raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_hand_raise_success() -> None:
    """kutana_cancel_hand_raise returns 'cancelled' when removed from queue."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(in_queue=True, queue_position=2)
    tm.cancel_hand_raise.return_value = True

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_cancel_hand_raise(str(TEST_MEETING_ID)))

    assert result["status"] == "cancelled"
    assert result["was_position"] == 2

    tm.cancel_hand_raise.assert_awaited_once_with(TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, None)


@pytest.mark.asyncio
async def test_cancel_hand_raise_not_in_queue() -> None:
    """kutana_cancel_hand_raise returns 'not_in_queue' when not in queue."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(in_queue=False)
    tm.cancel_hand_raise.return_value = False

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_cancel_hand_raise(str(TEST_MEETING_ID)))

    assert result["status"] == "not_in_queue"
    assert result["was_position"] is None


@pytest.mark.asyncio
async def test_cancel_hand_raise_with_specific_id() -> None:
    """kutana_cancel_hand_raise passes hand_raise_id to TurnManager when provided."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(in_queue=True, queue_position=1)
    tm.cancel_hand_raise.return_value = True

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await kutana_cancel_hand_raise(str(TEST_MEETING_ID), hand_raise_id=str(TEST_HAND_RAISE_ID))

    tm.cancel_hand_raise.assert_awaited_once_with(
        TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, TEST_HAND_RAISE_ID
    )


# ---------------------------------------------------------------------------
# kutana_get_speaking_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_speaking_status_is_speaking() -> None:
    """kutana_get_speaking_status returns is_speaking=True for active speaker."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(is_speaking=True)
    tm.get_active_speaker.return_value = TEST_AGENT_CONFIG_ID

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_get_speaking_status(str(TEST_MEETING_ID)))

    assert result["is_speaking"] is True
    assert result["is_in_queue"] is False
    assert result["current_speaker"] == str(TEST_AGENT_CONFIG_ID)
    assert result["meeting_phase"] == "active"


@pytest.mark.asyncio
async def test_get_speaking_status_in_queue() -> None:
    """kutana_get_speaking_status returns correct queue position when waiting."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(
        is_speaking=False, in_queue=True, queue_position=3
    )
    tm.get_active_speaker.return_value = TEST_PARTICIPANT_A

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_get_speaking_status(str(TEST_MEETING_ID)))

    assert result["is_speaking"] is False
    assert result["is_in_queue"] is True
    assert result["queue_position"] == 3
    assert result["current_speaker"] == str(TEST_PARTICIPANT_A)


@pytest.mark.asyncio
async def test_get_speaking_status_idle() -> None:
    """kutana_get_speaking_status returns idle state when not speaking or in queue."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status()
    tm.get_active_speaker.return_value = None

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_get_speaking_status(str(TEST_MEETING_ID)))

    assert result["is_speaking"] is False
    assert result["is_in_queue"] is False
    assert result["queue_position"] is None
    assert result["current_speaker"] is None


# ---------------------------------------------------------------------------
# kutana_start_speaking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_speaking_as_active_speaker() -> None:
    """kutana_start_speaking returns status=speaking with started_at when agent is active speaker."""
    tm = _make_turn_manager()
    tm.start_speaking.return_value = _STARTED_AT

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_start_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "speaking"
    assert result["started_at"] == _STARTED_AT.isoformat()

    tm.start_speaking.assert_awaited_once_with(TEST_MEETING_ID, TEST_AGENT_CONFIG_ID)


@pytest.mark.asyncio
async def test_start_speaking_not_active_speaker() -> None:
    """kutana_start_speaking returns status=not_your_turn when not the active speaker."""
    tm = _make_turn_manager()
    tm.start_speaking.return_value = None

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_start_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "not_your_turn"
    assert result["started_at"] is None

    tm.start_speaking.assert_awaited_once_with(TEST_MEETING_ID, TEST_AGENT_CONFIG_ID)


@pytest.mark.asyncio
async def test_start_speaking_started_at_is_iso_string() -> None:
    """kutana_start_speaking started_at is a valid ISO 8601 string."""
    from datetime import UTC, datetime

    tm = _make_turn_manager()
    expected_dt = datetime(2026, 3, 23, 15, 30, 0, tzinfo=UTC)
    tm.start_speaking.return_value = expected_dt

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await kutana_start_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "speaking"
    # Should be parseable as ISO 8601
    parsed = datetime.fromisoformat(result["started_at"])
    assert parsed == expected_dt


# ---------------------------------------------------------------------------
# kutana_join_meeting — capabilities mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_join_meeting_text_only_default_capabilities() -> None:
    """kutana_join_meeting maps text_only to listen+transcribe gateway caps."""
    mapped_caps: list[str] = []

    async def fake_connect_and_join(
        meeting_id: str,
        capabilities: list[str] | None = None,
        source: str = "claude-code",
    ) -> dict:
        nonlocal mapped_caps
        mapped_caps = capabilities or []
        return {
            "type": "joined",
            "meeting_id": meeting_id,
            "granted_capabilities": capabilities or [],
        }

    mock_gw = MagicMock()
    mock_gw.meeting_id = None
    mock_gw.connect_and_join = AsyncMock(side_effect=fake_connect_and_join)

    mock_client = MagicMock()
    mock_client.exchange_for_gateway_token = AsyncMock(return_value="gw-token")

    with (
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_api_client", mock_client),
        patch.object(main_module, "_gateway_client", None),
        patch("mcp_server.main.GatewayClient", return_value=mock_gw),
    ):
        from mcp_server.main import kutana_join_meeting

        await kutana_join_meeting(str(TEST_MEETING_ID), capabilities=["text_only"])

    assert set(mapped_caps) == {"listen", "transcribe"}


@pytest.mark.asyncio
async def test_join_meeting_voice_returns_audio_fields() -> None:
    """kutana_join_meeting returns audio_ws_url and audio_token for voice."""

    async def fake_connect_and_join(
        meeting_id: str,
        capabilities: list[str] | None = None,
        source: str = "claude-code",
    ) -> dict:
        return {
            "type": "joined",
            "meeting_id": meeting_id,
            "granted_capabilities": capabilities or [],
        }

    mock_gw = MagicMock()
    mock_gw.meeting_id = None
    mock_gw.connect_and_join = AsyncMock(side_effect=fake_connect_and_join)

    mock_client = MagicMock()
    mock_client.exchange_for_gateway_token = AsyncMock(return_value="gw-token-voice")

    with (
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_api_client", mock_client),
        patch.object(main_module, "_gateway_client", None),
        patch("mcp_server.main.GatewayClient", return_value=mock_gw),
    ):
        from mcp_server.main import kutana_join_meeting

        result = json.loads(await kutana_join_meeting(str(TEST_MEETING_ID), capabilities=["voice"]))

    assert "audio_ws_url" in result
    assert "audio_token" in result
    assert result["audio_token"] == "gw-token-voice"


@pytest.mark.asyncio
async def test_join_meeting_text_only_no_audio_fields() -> None:
    """kutana_join_meeting does not include audio fields for text_only."""

    async def fake_connect_and_join(
        meeting_id: str,
        capabilities: list[str] | None = None,
        source: str = "claude-code",
    ) -> dict:
        return {
            "type": "joined",
            "meeting_id": meeting_id,
            "granted_capabilities": capabilities or [],
        }

    mock_gw = MagicMock()
    mock_gw.meeting_id = None
    mock_gw.connect_and_join = AsyncMock(side_effect=fake_connect_and_join)

    mock_client = MagicMock()
    mock_client.exchange_for_gateway_token = AsyncMock(return_value="gw-token")

    with (
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_api_client", mock_client),
        patch.object(main_module, "_gateway_client", None),
        patch("mcp_server.main.GatewayClient", return_value=mock_gw),
    ):
        from mcp_server.main import kutana_join_meeting

        result = json.loads(
            await kutana_join_meeting(str(TEST_MEETING_ID), capabilities=["text_only"])
        )

    assert "audio_ws_url" not in result
    assert "audio_token" not in result


@pytest.mark.asyncio
async def test_join_meeting_voice_includes_speak_cap() -> None:
    """kutana_join_meeting maps voice to include speak capability."""
    mapped_caps: list[str] = []

    async def fake_connect_and_join(
        meeting_id: str,
        capabilities: list[str] | None = None,
        source: str = "claude-code",
    ) -> dict:
        nonlocal mapped_caps
        mapped_caps = capabilities or []
        return {"type": "joined", "meeting_id": meeting_id, "granted_capabilities": []}

    mock_gw = MagicMock()
    mock_gw.meeting_id = None
    mock_gw.connect_and_join = AsyncMock(side_effect=fake_connect_and_join)

    mock_client = MagicMock()
    mock_client.exchange_for_gateway_token = AsyncMock(return_value="token")

    with (
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_api_client", mock_client),
        patch.object(main_module, "_gateway_client", None),
        patch("mcp_server.main.GatewayClient", return_value=mock_gw),
    ):
        from mcp_server.main import kutana_join_meeting

        await kutana_join_meeting(str(TEST_MEETING_ID), capabilities=["voice"])

    assert "speak" in mapped_caps
    assert "listen" in mapped_caps
    assert "transcribe" in mapped_caps
