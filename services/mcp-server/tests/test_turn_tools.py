"""Unit tests for Turn Management MCP tools.

Tests each of the 5 turn management tools by mocking the RedisTurnManager
and MCPIdentity globals in mcp_server.main.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

import mcp_server.main as main_module
from mcp_server.auth import MCPIdentity
from mcp_server.main import (
    cancel_hand_raise,
    get_queue_status,
    get_speaking_status,
    mark_finished_speaking,
    raise_hand,
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
    return tm


# ---------------------------------------------------------------------------
# raise_hand
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
        result = json.loads(await raise_hand(str(TEST_MEETING_ID)))

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
        result = json.loads(await raise_hand(str(TEST_MEETING_ID)))

    assert result["queue_position"] == 0
    assert result["current_speaker"] == str(TEST_AGENT_CONFIG_ID)


@pytest.mark.asyncio
async def test_raise_hand_urgent_with_topic() -> None:
    """raise_hand passes priority and topic through to TurnManager."""
    tm = _make_turn_manager()
    tm.raise_hand.return_value = _make_raise_hand_result(queue_position=1)
    tm.get_active_speaker.return_value = None

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await raise_hand(str(TEST_MEETING_ID), priority="urgent", topic="Budget update")

    tm.raise_hand.assert_awaited_once_with(
        TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, priority="urgent", topic="Budget update"
    )


# ---------------------------------------------------------------------------
# get_queue_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_queue_status_with_entries() -> None:
    """get_queue_status returns ordered queue and your_position."""
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
        result = json.loads(await get_queue_status(str(TEST_MEETING_ID)))

    assert result["current_speaker"] == str(TEST_PARTICIPANT_B)
    assert result["total_in_queue"] == 2
    assert result["your_position"] == 2
    assert result["queue"][0]["position"] == 1
    assert result["queue"][0]["participant_id"] == str(TEST_PARTICIPANT_A)
    assert result["queue"][0]["topic"] == "Agenda"
    assert result["queue"][1]["position"] == 2


@pytest.mark.asyncio
async def test_get_queue_status_empty() -> None:
    """get_queue_status with empty queue returns nulls."""
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_queue_status(str(TEST_MEETING_ID)))

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
        result = json.loads(await get_queue_status(str(TEST_MEETING_ID)))

    assert result["your_position"] is None
    assert result["total_in_queue"] == 1


# ---------------------------------------------------------------------------
# mark_finished_speaking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_finished_speaking_with_next() -> None:
    """mark_finished_speaking returns next_speaker when queue has entries."""
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
        result = json.loads(await mark_finished_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "finished"
    assert result["next_speaker"] == str(TEST_PARTICIPANT_A)
    assert result["queue_remaining"] == 1

    tm.mark_finished_speaking.assert_awaited_once_with(TEST_MEETING_ID, TEST_AGENT_CONFIG_ID)


@pytest.mark.asyncio
async def test_mark_finished_speaking_empty_queue() -> None:
    """mark_finished_speaking returns null next_speaker when queue empties."""
    tm = _make_turn_manager()
    tm.mark_finished_speaking.return_value = None
    tm.get_queue_status.return_value = _make_queue_status()

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await mark_finished_speaking(str(TEST_MEETING_ID)))

    assert result["status"] == "finished"
    assert result["next_speaker"] is None
    assert result["queue_remaining"] == 0


# ---------------------------------------------------------------------------
# cancel_hand_raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_hand_raise_success() -> None:
    """cancel_hand_raise returns 'cancelled' when removed from queue."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(in_queue=True, queue_position=2)
    tm.cancel_hand_raise.return_value = True

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await cancel_hand_raise(str(TEST_MEETING_ID)))

    assert result["status"] == "cancelled"
    assert result["was_position"] == 2

    tm.cancel_hand_raise.assert_awaited_once_with(TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, None)


@pytest.mark.asyncio
async def test_cancel_hand_raise_not_in_queue() -> None:
    """cancel_hand_raise returns 'not_in_queue' when not in queue."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(in_queue=False)
    tm.cancel_hand_raise.return_value = False

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await cancel_hand_raise(str(TEST_MEETING_ID)))

    assert result["status"] == "not_in_queue"
    assert result["was_position"] is None


@pytest.mark.asyncio
async def test_cancel_hand_raise_with_specific_id() -> None:
    """cancel_hand_raise passes hand_raise_id to TurnManager when provided."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(in_queue=True, queue_position=1)
    tm.cancel_hand_raise.return_value = True

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await cancel_hand_raise(str(TEST_MEETING_ID), hand_raise_id=str(TEST_HAND_RAISE_ID))

    tm.cancel_hand_raise.assert_awaited_once_with(
        TEST_MEETING_ID, TEST_AGENT_CONFIG_ID, TEST_HAND_RAISE_ID
    )


# ---------------------------------------------------------------------------
# get_speaking_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_speaking_status_is_speaking() -> None:
    """get_speaking_status returns is_speaking=True for active speaker."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(is_speaking=True)
    tm.get_active_speaker.return_value = TEST_AGENT_CONFIG_ID

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_speaking_status(str(TEST_MEETING_ID)))

    assert result["is_speaking"] is True
    assert result["is_in_queue"] is False
    assert result["current_speaker"] == str(TEST_AGENT_CONFIG_ID)
    assert result["meeting_phase"] == "active"


@pytest.mark.asyncio
async def test_get_speaking_status_in_queue() -> None:
    """get_speaking_status returns correct queue position when waiting."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status(
        is_speaking=False, in_queue=True, queue_position=3
    )
    tm.get_active_speaker.return_value = TEST_PARTICIPANT_A

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_speaking_status(str(TEST_MEETING_ID)))

    assert result["is_speaking"] is False
    assert result["is_in_queue"] is True
    assert result["queue_position"] == 3
    assert result["current_speaker"] == str(TEST_PARTICIPANT_A)


@pytest.mark.asyncio
async def test_get_speaking_status_idle() -> None:
    """get_speaking_status returns idle state when not speaking or in queue."""
    tm = _make_turn_manager()
    tm.get_speaking_status.return_value = _make_speaking_status()
    tm.get_active_speaker.return_value = None

    with (
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_speaking_status(str(TEST_MEETING_ID)))

    assert result["is_speaking"] is False
    assert result["is_in_queue"] is False
    assert result["queue_position"] is None
    assert result["current_speaker"] is None
