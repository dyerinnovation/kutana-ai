"""Redis-backed turn management provider.

Uses Redis sorted sets for FIFO queue ordering with priority support,
and Redis strings/hashes for active speaker state. Critical operations
(raise_hand, mark_finished_speaking) use Lua scripts for atomicity.

Key schema:
    turn:{meeting_id}:queue          ZSET  score=priority_ts, member="pid:hrid"
    turn:{meeting_id}:speaker        STRING  participant_id
    turn:{meeting_id}:speaker_since  STRING  float timestamp
    turn:{meeting_id}:hand:{pid}     STRING  hand_raise_id (presence key)
    turn:{meeting_id}:meta:{hrid}    HASH    participant_id, priority, topic, raised_at

Priority scoring:
    URGENT: score = timestamp
    NORMAL: score = PRIORITY_OFFSET + timestamp  (sorts after urgent)
    PRIORITY_OFFSET = 2_000_000_000_000
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import redis.asyncio as aioredis

from convene_core.interfaces.turn_manager import TurnManager
from convene_core.models.turn import (
    HandRaisePriority,
    QueueEntry,
    QueueStatus,
    RaiseHandResult,
    SpeakingStatus,
)

logger = logging.getLogger(__name__)

# Urgent entries score at raw timestamp; normal entries score at this offset + timestamp.
# Current timestamps are ~1.7e9, so offset of 2e12 ensures urgent always sorts first.
_PRIORITY_OFFSET: float = 2_000_000_000_000.0

# UUID string length (hyphenated form): "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
_UUID_LEN: int = 36

# ---------------------------------------------------------------------------
# Lua scripts (executed atomically on the Redis server)
# ---------------------------------------------------------------------------

# Atomically check-and-add to queue, then promote if no active speaker.
# Returns: ["promoted"|"added"|"already", hand_raise_id, str(queue_position)]
_RAISE_HAND_SCRIPT = """
local queue_key    = KEYS[1]
local hand_key     = KEYS[2]
local meta_key     = KEYS[3]
local speaker_key  = KEYS[4]
local since_key    = KEYS[5]

local score        = tonumber(ARGV[1])
local member       = ARGV[2]
local hand_raise_id = ARGV[3]
local pid          = ARGV[4]
local priority     = ARGV[5]
local topic        = ARGV[6]
local raised_at    = ARGV[7]
local now_ts       = ARGV[8]

-- If participant already has a hand raise registered, return their position
local existing = redis.call('GET', hand_key)
if existing then
    local existing_member = pid .. ':' .. existing
    local rank = redis.call('ZRANK', queue_key, existing_member)
    if rank then
        return {'already', existing, tostring(rank + 1)}
    end
    -- They were promoted (in speaker slot, not in queue)
    return {'already', existing, '0'}
end

-- Add to queue
redis.call('ZADD', queue_key, score, member)
redis.call('SET', hand_key, hand_raise_id)
redis.call('HSET', meta_key,
    'participant_id', pid,
    'priority', priority,
    'topic', topic,
    'raised_at', raised_at)

-- Get current 1-based position
local rank = redis.call('ZRANK', queue_key, member)

-- Check if anyone is already speaking
local speaker = redis.call('GET', speaker_key)
if not speaker then
    -- No active speaker: immediately promote this participant
    redis.call('ZPOPMIN', queue_key, 1)
    redis.call('DEL', hand_key)
    redis.call('SET', speaker_key, pid)
    redis.call('SET', since_key, now_ts)
    return {'promoted', hand_raise_id, '0'}
end

return {'added', hand_raise_id, tostring(rank + 1)}
"""

# Atomically verify active speaker, clear them, pop next, and promote.
# Returns: ["not_speaker"]  |  ["done"]  |  ["advanced", new_pid]
_FINISH_SPEAKING_SCRIPT = """
local speaker_key  = KEYS[1]
local since_key    = KEYS[2]
local queue_key    = KEYS[3]
local hand_prefix  = KEYS[4]

local pid    = ARGV[1]
local now_ts = ARGV[2]

-- Verify this participant is the active speaker
local speaker = redis.call('GET', speaker_key)
if not speaker or speaker ~= pid then
    return {'not_speaker'}
end

-- Clear current speaker
redis.call('DEL', speaker_key)
redis.call('DEL', since_key)

-- Pop next participant from queue (lowest score = highest priority)
local next_items = redis.call('ZPOPMIN', queue_key, 1)
if #next_items == 0 then
    return {'done'}
end

-- Parse member: "participant_id:hand_raise_id" (UUID:UUID)
local member = next_items[1]
local next_pid = string.sub(member, 1, 36)

-- Set as new active speaker
redis.call('SET', speaker_key, next_pid)
redis.call('SET', since_key, now_ts)

-- Remove their hand-presence key (they are now the active speaker)
redis.call('DEL', hand_prefix .. next_pid)

return {'advanced', next_pid}
"""


class RedisTurnManager(TurnManager):
    """Redis-backed implementation of TurnManager.

    Uses sorted sets for ordered queue management and Lua scripts
    for atomic raise/finish operations.

    Args:
        redis_url: Redis connection URL (e.g., "redis://localhost:6379/0").
        speaker_timeout_seconds: Auto-advance timeout in seconds (default 300).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        speaker_timeout_seconds: int = 300,
    ) -> None:
        """Initialise the Redis turn manager.

        Args:
            redis_url: Redis connection URL.
            speaker_timeout_seconds: Seconds before auto-advance on timeout.
        """
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None  # type: ignore[type-arg]
        self.speaker_timeout_seconds = speaker_timeout_seconds
        self._raise_hand_script: aioredis.client.Script | None = None
        self._finish_speaking_script: aioredis.client.Script | None = None

    async def _get_redis(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Return (and lazily initialise) the Redis client."""
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            self._raise_hand_script = self._redis.register_script(_RAISE_HAND_SCRIPT)
            self._finish_speaking_script = self._redis.register_script(_FINISH_SPEAKING_SCRIPT)
        return self._redis

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _queue_key(meeting_id: UUID) -> str:
        return f"turn:{meeting_id}:queue"

    @staticmethod
    def _speaker_key(meeting_id: UUID) -> str:
        return f"turn:{meeting_id}:speaker"

    @staticmethod
    def _since_key(meeting_id: UUID) -> str:
        return f"turn:{meeting_id}:speaker_since"

    @staticmethod
    def _hand_key(meeting_id: UUID, participant_id: UUID) -> str:
        return f"turn:{meeting_id}:hand:{participant_id}"

    @staticmethod
    def _hand_prefix(meeting_id: UUID) -> str:
        """Prefix for all hand keys in a meeting (used in Lua)."""
        return f"turn:{meeting_id}:hand:"

    @staticmethod
    def _meta_key(meeting_id: UUID, hand_raise_id: UUID) -> str:
        return f"turn:{meeting_id}:meta:{hand_raise_id}"

    @staticmethod
    def _priority_score(priority: str) -> float:
        """Compute the sorted-set score for a priority level.

        Urgent entries score at raw timestamp (low → sorts first).
        Normal entries score at OFFSET + timestamp (high → sorts last).
        Within each priority tier, FIFO ordering is preserved.
        """
        ts = time.time()
        if priority == HandRaisePriority.URGENT:
            return ts
        return _PRIORITY_OFFSET + ts

    # ------------------------------------------------------------------
    # TurnManager interface
    # ------------------------------------------------------------------

    async def raise_hand(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        priority: str = "normal",
        topic: str | None = None,
    ) -> RaiseHandResult:
        """Add a participant to the speaking queue.

        Args:
            meeting_id: The meeting to raise a hand in.
            participant_id: The participant raising their hand.
            priority: "normal" (FIFO) or "urgent" (front of queue).
            topic: Optional topic string.

        Returns:
            RaiseHandResult with position and hand_raise_id.
        """
        r = await self._get_redis()
        hand_raise_id = uuid4()
        score = self._priority_score(priority)
        member = f"{participant_id}:{hand_raise_id}"
        now_ts = str(time.time())
        raised_at = datetime.now(tz=UTC).isoformat()

        result: list[str] = await self._raise_hand_script(  # type: ignore[index]
            keys=[
                self._queue_key(meeting_id),
                self._hand_key(meeting_id, participant_id),
                self._meta_key(meeting_id, hand_raise_id),
                self._speaker_key(meeting_id),
                self._since_key(meeting_id),
            ],
            args=[
                str(score),
                member,
                str(hand_raise_id),
                str(participant_id),
                priority,
                topic or "",
                raised_at,
                now_ts,
            ],
        )

        status = result[0]
        returned_hrid = UUID(result[1])
        position = int(result[2])

        if status == "already":
            logger.debug(
                "Participant %s already in queue for meeting %s at position %d",
                participant_id,
                meeting_id,
                position,
            )
            return RaiseHandResult(
                queue_position=position,
                hand_raise_id=returned_hrid,
                was_promoted=False,
            )

        if status == "promoted":
            logger.info(
                "Participant %s immediately promoted to speaker in meeting %s",
                participant_id,
                meeting_id,
            )
            return RaiseHandResult(
                queue_position=0,
                hand_raise_id=returned_hrid,
                was_promoted=True,
            )

        # status == "added"
        logger.info(
            "Participant %s added to queue for meeting %s at position %d",
            participant_id,
            meeting_id,
            position,
        )
        return RaiseHandResult(
            queue_position=position,
            hand_raise_id=returned_hrid,
            was_promoted=False,
        )

    async def get_queue_status(self, meeting_id: UUID) -> QueueStatus:
        """Get the current queue state for a meeting.

        Args:
            meeting_id: The meeting to query.

        Returns:
            QueueStatus with active speaker and ordered queue entries.
        """
        r = await self._get_redis()

        speaker_str, members_with_scores = await asyncio.gather(
            r.get(self._speaker_key(meeting_id)),
            r.zrange(self._queue_key(meeting_id), 0, -1, withscores=True),
        )

        active_speaker_id = UUID(speaker_str) if speaker_str else None

        queue: list[QueueEntry] = []
        for position, (member, _score) in enumerate(members_with_scores, start=1):
            pid_str, hrid_str = member[:_UUID_LEN], member[_UUID_LEN + 1:]
            meta = await r.hgetall(self._meta_key(meeting_id, UUID(hrid_str)))
            raised_at_str = meta.get("raised_at", datetime.now(tz=UTC).isoformat())
            raised_at = datetime.fromisoformat(raised_at_str)
            queue.append(
                QueueEntry(
                    participant_id=UUID(pid_str),
                    hand_raise_id=UUID(hrid_str),
                    priority=HandRaisePriority(meta.get("priority", "normal")),
                    topic=meta.get("topic") or None,
                    raised_at=raised_at,
                    position=position,
                )
            )

        return QueueStatus(
            meeting_id=meeting_id,
            active_speaker_id=active_speaker_id,
            queue=queue,
        )

    async def get_speaking_status(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> SpeakingStatus:
        """Get the speaking status of a specific participant.

        Args:
            meeting_id: The meeting to query.
            participant_id: The participant to check.

        Returns:
            SpeakingStatus with is_speaking, in_queue, and queue position.
        """
        r = await self._get_redis()
        speaker_str, hrid_str = await asyncio.gather(
            r.get(self._speaker_key(meeting_id)),
            r.get(self._hand_key(meeting_id, participant_id)),
        )

        is_speaking = speaker_str == str(participant_id)

        if is_speaking:
            return SpeakingStatus(
                participant_id=participant_id,
                is_speaking=True,
                in_queue=False,
                queue_position=None,
                hand_raise_id=None,
            )

        if hrid_str:
            hand_raise_id = UUID(hrid_str)
            member = f"{participant_id}:{hand_raise_id}"
            rank = await r.zrank(self._queue_key(meeting_id), member)
            queue_position = (rank + 1) if rank is not None else None
            return SpeakingStatus(
                participant_id=participant_id,
                is_speaking=False,
                in_queue=True,
                queue_position=queue_position,
                hand_raise_id=hand_raise_id,
            )

        return SpeakingStatus(
            participant_id=participant_id,
            is_speaking=False,
            in_queue=False,
            queue_position=None,
            hand_raise_id=None,
        )

    async def mark_finished_speaking(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> UUID | None:
        """Mark the active speaker as done and advance to the next in queue.

        Args:
            meeting_id: The meeting.
            participant_id: The participant finishing their turn.

        Returns:
            UUID of the new active speaker, or None if queue is empty.
        """
        result: list[str] = await self._finish_speaking_script(  # type: ignore[index]
            keys=[
                self._speaker_key(meeting_id),
                self._since_key(meeting_id),
                self._queue_key(meeting_id),
                self._hand_prefix(meeting_id),
            ],
            args=[
                str(participant_id),
                str(time.time()),
            ],
        )

        status = result[0]

        if status == "not_speaker":
            logger.debug(
                "mark_finished_speaking: %s is not the active speaker in meeting %s",
                participant_id,
                meeting_id,
            )
            return None

        if status == "done":
            logger.info("Queue empty after speaker %s finished in meeting %s", participant_id, meeting_id)
            return None

        # status == "advanced"
        new_speaker_id = UUID(result[1])
        logger.info(
            "Speaker advanced: %s finished, %s is next in meeting %s",
            participant_id,
            new_speaker_id,
            meeting_id,
        )
        return new_speaker_id

    async def cancel_hand_raise(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        hand_raise_id: UUID | None = None,
    ) -> bool:
        """Remove a participant from the speaking queue.

        Args:
            meeting_id: The meeting.
            participant_id: The participant lowering their hand.
            hand_raise_id: Specific raise to cancel (None = cancel current).

        Returns:
            True if removed, False if not in queue.
        """
        r = await self._get_redis()
        hand_key = self._hand_key(meeting_id, participant_id)

        if hand_raise_id is None:
            hrid_str = await r.get(hand_key)
            if not hrid_str:
                return False
            hand_raise_id = UUID(hrid_str)

        member = f"{participant_id}:{hand_raise_id}"
        queue_key = self._queue_key(meeting_id)
        meta_key = self._meta_key(meeting_id, hand_raise_id)

        async with r.pipeline(transaction=True) as pipe:
            pipe.zrem(queue_key, member)
            pipe.delete(hand_key)
            pipe.delete(meta_key)
            results = await pipe.execute()

        removed = results[0] > 0
        if removed:
            logger.info(
                "Participant %s cancelled hand raise %s in meeting %s",
                participant_id,
                hand_raise_id,
                meeting_id,
            )
        return removed

    async def set_active_speaker(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> None:
        """Manually set the active speaker (host override).

        Args:
            meeting_id: The meeting.
            participant_id: The participant to set as active speaker.
        """
        r = await self._get_redis()
        async with r.pipeline(transaction=True) as pipe:
            pipe.set(self._speaker_key(meeting_id), str(participant_id))
            pipe.set(self._since_key(meeting_id), str(time.time()))
            await pipe.execute()
        logger.info(
            "Active speaker manually set to %s in meeting %s",
            participant_id,
            meeting_id,
        )

    async def get_active_speaker(self, meeting_id: UUID) -> UUID | None:
        """Get the current active speaker's participant ID.

        Args:
            meeting_id: The meeting to query.

        Returns:
            UUID of the active speaker, or None if no one is speaking.
        """
        r = await self._get_redis()
        value = await r.get(self._speaker_key(meeting_id))
        return UUID(value) if value else None

    async def get_speaker_elapsed_seconds(self, meeting_id: UUID) -> float | None:
        """Return how long the current speaker has been speaking, in seconds.

        Args:
            meeting_id: The meeting to query.

        Returns:
            Elapsed seconds, or None if no one is currently speaking.
        """
        r = await self._get_redis()
        since_str = await r.get(self._since_key(meeting_id))
        if since_str is None:
            return None
        return time.time() - float(since_str)

    async def clear_meeting(self, meeting_id: UUID) -> None:
        """Clear all turn management state for a meeting.

        Args:
            meeting_id: The meeting to clear.
        """
        r = await self._get_redis()
        pattern = f"turn:{meeting_id}:*"
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
        logger.info("Cleared turn management state for meeting %s (%d keys)", meeting_id, len(keys))
