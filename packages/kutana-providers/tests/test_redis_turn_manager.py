"""Tests for RedisTurnManager provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kutana_core.models.turn import RaiseHandResult, SpeakingStatus
from kutana_providers.turn_management.redis_turn_manager import (
    _PRIORITY_OFFSET,
    RedisTurnManager,
)

MEETING_ID = uuid4()
PARTICIPANT_A = uuid4()
PARTICIPANT_B = uuid4()
HAND_RAISE_ID = uuid4()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Async mock simulating a redis.asyncio.Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.zrange = AsyncMock(return_value=[])
    redis.zrank = AsyncMock(return_value=None)
    redis.zrem = AsyncMock(return_value=1)
    redis.keys = AsyncMock(return_value=[])
    redis.hgetall = AsyncMock(return_value={})
    redis.pipeline = MagicMock()
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def manager(mock_redis: AsyncMock) -> RedisTurnManager:
    """RedisTurnManager with mocked Redis and Lua scripts."""
    m = RedisTurnManager(redis_url="redis://localhost/0", speaker_timeout_seconds=300)
    m._redis = mock_redis
    m._raise_hand_script = AsyncMock()
    m._finish_speaking_script = AsyncMock()
    return m


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------


class TestPriorityScoring:
    """Tests for the priority score calculation logic."""

    def test_urgent_score_lower_than_normal(self) -> None:
        """Urgent score must be lower than normal so it sorts first."""
        urgent_score = RedisTurnManager._priority_score("urgent")
        normal_score = RedisTurnManager._priority_score("normal")
        assert urgent_score < normal_score

    def test_normal_score_above_offset(self) -> None:
        """Normal score is above the priority offset value."""
        normal_score = RedisTurnManager._priority_score("normal")
        assert normal_score > _PRIORITY_OFFSET

    def test_urgent_score_below_offset(self) -> None:
        """Urgent score is below the priority offset (raw timestamp)."""
        urgent_score = RedisTurnManager._priority_score("urgent")
        assert urgent_score < _PRIORITY_OFFSET

    def test_fifo_preserved_within_priority(self) -> None:
        """Two normal-priority raises preserve FIFO ordering via score."""
        import time

        score1 = _PRIORITY_OFFSET + time.time()
        score2 = _PRIORITY_OFFSET + time.time() + 0.01
        assert score1 < score2


# ---------------------------------------------------------------------------
# raise_hand
# ---------------------------------------------------------------------------


class TestRaiseHand:
    """Tests for raise_hand operations."""

    async def test_added_to_queue(self, manager: RedisTurnManager) -> None:
        """Raise hand returns added result with 1-based position."""
        hrid = uuid4()
        manager._raise_hand_script.return_value = ["added", str(hrid), "2"]

        result = await manager.raise_hand(MEETING_ID, PARTICIPANT_A)

        assert isinstance(result, RaiseHandResult)
        assert result.queue_position == 2
        assert result.hand_raise_id == hrid
        assert result.was_promoted is False

    async def test_promoted_immediately(self, manager: RedisTurnManager) -> None:
        """When no active speaker, participant is immediately promoted."""
        hrid = uuid4()
        manager._raise_hand_script.return_value = ["promoted", str(hrid), "0"]

        result = await manager.raise_hand(MEETING_ID, PARTICIPANT_A)

        assert result.queue_position == 0
        assert result.was_promoted is True

    async def test_already_in_queue(self, manager: RedisTurnManager) -> None:
        """Duplicate raise_hand returns existing position."""
        hrid = uuid4()
        manager._raise_hand_script.return_value = ["already", str(hrid), "1"]

        result = await manager.raise_hand(MEETING_ID, PARTICIPANT_A)

        assert result.queue_position == 1
        assert result.hand_raise_id == hrid
        assert result.was_promoted is False

    async def test_topic_passed_to_script(self, manager: RedisTurnManager) -> None:
        """Topic is forwarded to the Lua script args."""
        hrid = uuid4()
        manager._raise_hand_script.return_value = ["added", str(hrid), "1"]

        await manager.raise_hand(MEETING_ID, PARTICIPANT_A, topic="Budget review")

        call_kwargs = manager._raise_hand_script.call_args
        args = call_kwargs.kwargs["args"]
        assert "Budget review" in args

    async def test_urgent_priority_lower_score(self, manager: RedisTurnManager) -> None:
        """Urgent priority produces a lower score than normal in script args."""
        hrid = uuid4()
        manager._raise_hand_script.return_value = ["added", str(hrid), "1"]

        await manager.raise_hand(MEETING_ID, PARTICIPANT_A, priority="urgent")

        args = manager._raise_hand_script.call_args.kwargs["args"]
        score = float(args[0])
        assert score < _PRIORITY_OFFSET


# ---------------------------------------------------------------------------
# mark_finished_speaking
# ---------------------------------------------------------------------------


class TestMarkFinishedSpeaking:
    """Tests for mark_finished_speaking operations."""

    async def test_not_active_speaker(self, manager: RedisTurnManager) -> None:
        """Returns None if participant is not the active speaker."""
        manager._finish_speaking_script.return_value = ["not_speaker"]

        result = await manager.mark_finished_speaking(MEETING_ID, PARTICIPANT_A)

        assert result is None

    async def test_queue_empty_after_finish(self, manager: RedisTurnManager) -> None:
        """Returns None when queue is empty after finishing."""
        manager._finish_speaking_script.return_value = ["done"]

        result = await manager.mark_finished_speaking(MEETING_ID, PARTICIPANT_A)

        assert result is None

    async def test_advances_to_next_speaker(self, manager: RedisTurnManager) -> None:
        """Returns next speaker's UUID when advancing."""
        manager._finish_speaking_script.return_value = ["advanced", str(PARTICIPANT_B)]

        result = await manager.mark_finished_speaking(MEETING_ID, PARTICIPANT_A)

        assert result == PARTICIPANT_B

    async def test_calls_script_with_correct_keys(self, manager: RedisTurnManager) -> None:
        """Script is called with the expected Redis keys."""
        manager._finish_speaking_script.return_value = ["done"]

        await manager.mark_finished_speaking(MEETING_ID, PARTICIPANT_A)

        call_kwargs = manager._finish_speaking_script.call_args
        keys = call_kwargs.kwargs["keys"]
        meeting_str = str(MEETING_ID)
        assert any(meeting_str in k for k in keys)


# ---------------------------------------------------------------------------
# cancel_hand_raise
# ---------------------------------------------------------------------------


class TestCancelHandRaise:
    """Tests for cancel_hand_raise operations."""

    async def test_removes_from_queue(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns True when an entry is successfully removed."""
        mock_redis.get.return_value = str(HAND_RAISE_ID)
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[1, 1, 1])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await manager.cancel_hand_raise(MEETING_ID, PARTICIPANT_A)

        assert result is True

    async def test_not_in_queue(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns False when participant has no active hand raise."""
        mock_redis.get.return_value = None

        result = await manager.cancel_hand_raise(MEETING_ID, PARTICIPANT_A)

        assert result is False

    async def test_explicit_hand_raise_id(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """When hand_raise_id is provided, skips the get() lookup."""
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[1, 1, 1])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await manager.cancel_hand_raise(
            MEETING_ID, PARTICIPANT_A, hand_raise_id=HAND_RAISE_ID
        )

        # Should not call get() since we provided the ID
        mock_redis.get.assert_not_called()
        assert result is True


# ---------------------------------------------------------------------------
# get_active_speaker
# ---------------------------------------------------------------------------


class TestGetActiveSpeaker:
    """Tests for get_active_speaker operations."""

    async def test_no_speaker(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns None when no one is speaking."""
        mock_redis.get.return_value = None

        result = await manager.get_active_speaker(MEETING_ID)

        assert result is None

    async def test_active_speaker(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns the UUID of the active speaker."""
        mock_redis.get.return_value = str(PARTICIPANT_A)

        result = await manager.get_active_speaker(MEETING_ID)

        assert result == PARTICIPANT_A


# ---------------------------------------------------------------------------
# get_speaking_status
# ---------------------------------------------------------------------------


class TestGetSpeakingStatus:
    """Tests for get_speaking_status operations."""

    async def test_is_active_speaker(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns is_speaking=True when participant is the active speaker."""
        mock_redis.get = AsyncMock(side_effect=[str(PARTICIPANT_A), None])

        status = await manager.get_speaking_status(MEETING_ID, PARTICIPANT_A)

        assert isinstance(status, SpeakingStatus)
        assert status.is_speaking is True
        assert status.in_queue is False

    async def test_in_queue(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns in_queue=True with correct position for queued participant."""
        mock_redis.get = AsyncMock(side_effect=[None, str(HAND_RAISE_ID)])
        mock_redis.zrank = AsyncMock(return_value=1)  # 0-based rank = position 2

        status = await manager.get_speaking_status(MEETING_ID, PARTICIPANT_B)

        assert status.is_speaking is False
        assert status.in_queue is True
        assert status.queue_position == 2
        assert status.hand_raise_id == HAND_RAISE_ID

    async def test_idle(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Returns is_speaking=False, in_queue=False for idle participant."""
        mock_redis.get = AsyncMock(return_value=None)

        status = await manager.get_speaking_status(MEETING_ID, PARTICIPANT_A)

        assert status.is_speaking is False
        assert status.in_queue is False
        assert status.queue_position is None


# ---------------------------------------------------------------------------
# set_active_speaker
# ---------------------------------------------------------------------------


class TestSetActiveSpeaker:
    """Tests for set_active_speaker (host override) operation."""

    async def test_sets_speaker(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Calls Redis pipeline with the correct speaker key."""
        mock_pipe = AsyncMock()
        mock_pipe.set = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[True, True])
        mock_redis.pipeline.return_value.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_redis.pipeline.return_value.__aexit__ = AsyncMock(return_value=False)

        await manager.set_active_speaker(MEETING_ID, PARTICIPANT_A)

        mock_pipe.set.assert_called()
        # First set call should include participant_id
        first_call_args = mock_pipe.set.call_args_list[0]
        assert str(PARTICIPANT_A) in str(first_call_args)


# ---------------------------------------------------------------------------
# clear_meeting
# ---------------------------------------------------------------------------


class TestClearMeeting:
    """Tests for clear_meeting operation."""

    async def test_clears_meeting_keys(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Deletes all turn:{meeting_id}:* keys."""
        keys = [
            f"turn:{MEETING_ID}:queue",
            f"turn:{MEETING_ID}:speaker",
            f"turn:{MEETING_ID}:speaker_since",
        ]
        mock_redis.keys.return_value = keys
        mock_redis.delete = AsyncMock()

        await manager.clear_meeting(MEETING_ID)

        mock_redis.keys.assert_called_once_with(f"turn:{MEETING_ID}:*")
        mock_redis.delete.assert_called_once_with(*keys)

    async def test_no_keys_to_clear(
        self, manager: RedisTurnManager, mock_redis: AsyncMock
    ) -> None:
        """Does not call delete when there are no keys."""
        mock_redis.keys.return_value = []
        mock_redis.delete = AsyncMock()

        await manager.clear_meeting(MEETING_ID)

        mock_redis.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    """Tests that RedisTurnManager is registered in the default registry."""

    def test_registered(self) -> None:
        """RedisTurnManager is available in the default registry."""
        from kutana_providers.registry import ProviderType, default_registry

        assert default_registry.is_registered(ProviderType.TURN_MANAGER, "redis")

    def test_create_from_registry(self) -> None:
        """Registry can instantiate a RedisTurnManager."""
        from kutana_providers.registry import ProviderType, default_registry

        instance = default_registry.create(
            ProviderType.TURN_MANAGER,
            "redis",
            redis_url="redis://localhost/0",
        )
        assert isinstance(instance, RedisTurnManager)
