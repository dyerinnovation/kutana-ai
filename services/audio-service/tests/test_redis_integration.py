"""Integration tests for the audio pipeline → Redis event flow.

Requires a running Redis instance (docker compose up -d redis).
Tests are skipped when Redis is unavailable.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
import redis.asyncio as redis

from audio_service.audio_pipeline import AudioPipeline
from audio_service.event_publisher import STREAM_KEY, EventPublisher
from convene_core.models.transcript import TranscriptSegment
from convene_providers.testing import MockSTT

REDIS_URL = "redis://localhost:6379/0"


async def _redis_available() -> bool:
    """Check if Redis is reachable."""
    try:
        client: redis.Redis[str] = redis.from_url(
            REDIS_URL, decode_responses=True
        )
        await client.ping()
        await client.aclose()
        return True
    except (redis.ConnectionError, ConnectionRefusedError, OSError):
        return False


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def redis_client() -> redis.Redis[str]:
    """Create a Redis client, skip if unavailable."""
    if not await _redis_available():
        pytest.skip("Redis not available")

    client: redis.Redis[str] = redis.from_url(
        REDIS_URL, decode_responses=True
    )
    # Clean stream before test
    await client.delete(STREAM_KEY)
    yield client  # type: ignore[misc]
    # Clean up after test
    await client.delete(STREAM_KEY)
    await client.aclose()


def _make_segments(
    meeting_id: object, n: int = 2
) -> list[TranscriptSegment]:
    """Create sample transcript segments."""
    return [
        TranscriptSegment(
            meeting_id=meeting_id,  # type: ignore[arg-type]
            speaker_id=f"spk_{i}",
            text=f"Segment {i}",
            start_time=float(i * 10),
            end_time=float(i * 10 + 5),
            confidence=0.9,
        )
        for i in range(n)
    ]


class TestRedisEventFlow:
    """Integration tests for MockSTT → AudioPipeline → Redis."""

    async def test_meeting_lifecycle_events_in_redis(
        self, redis_client: redis.Redis[str]
    ) -> None:
        """Full lifecycle: MeetingStarted, 2 segments, MeetingEnded."""
        meeting_id = uuid4()
        segments = _make_segments(meeting_id, n=2)
        mock_stt = MockSTT(segments=segments)
        publisher = EventPublisher(redis_url=REDIS_URL)

        pipeline = AudioPipeline(
            stt_provider=mock_stt,
            event_publisher=publisher,
            meeting_id=meeting_id,
        )

        try:
            # Process some audio to trigger MeetingStarted
            await pipeline.process_audio(b"\x80" * 10)

            # Get transcript segments (triggers TranscriptSegmentFinal events)
            result = [seg async for seg in pipeline.get_segments()]
            assert len(result) == 2

            # Close triggers MeetingEnded
            await pipeline.close()

            # Read all events from stream
            entries = await redis_client.xrange(STREAM_KEY)
            assert len(entries) == 4

            event_types = [
                entry[1]["event_type"] for entry in entries
            ]
            assert event_types == [
                "meeting.started",
                "transcript.segment.final",
                "transcript.segment.final",
                "meeting.ended",
            ]

            # Verify meeting_id in events
            for entry in entries:
                payload = json.loads(entry[1]["payload"])
                assert payload["meeting_id"] == str(meeting_id)

            # Verify transcript text
            seg0_payload = json.loads(entries[1][1]["payload"])
            assert seg0_payload["segment"]["text"] == "Segment 0"

            seg1_payload = json.loads(entries[2][1]["payload"])
            assert seg1_payload["segment"]["text"] == "Segment 1"
        finally:
            await publisher.close()

    async def test_pipeline_without_publisher_no_redis_writes(
        self, redis_client: redis.Redis[str]
    ) -> None:
        """Pipeline without publisher writes nothing to Redis."""
        meeting_id = uuid4()
        segments = _make_segments(meeting_id, n=1)
        mock_stt = MockSTT(segments=segments)

        pipeline = AudioPipeline(
            stt_provider=mock_stt,
            event_publisher=None,
            meeting_id=meeting_id,
        )

        await pipeline.process_audio(b"\x80" * 10)
        _ = [seg async for seg in pipeline.get_segments()]
        await pipeline.close()

        entries = await redis_client.xrange(STREAM_KEY)
        assert len(entries) == 0

    async def test_multiple_meetings_produce_separate_events(
        self, redis_client: redis.Redis[str]
    ) -> None:
        """Two pipelines produce events with distinct meeting IDs."""
        mid_1 = uuid4()
        mid_2 = uuid4()
        publisher = EventPublisher(redis_url=REDIS_URL)

        try:
            # Pipeline 1
            stt_1 = MockSTT(segments=_make_segments(mid_1, n=1))
            pipe_1 = AudioPipeline(
                stt_provider=stt_1,
                event_publisher=publisher,
                meeting_id=mid_1,
            )
            await pipe_1.process_audio(b"\x80" * 10)
            _ = [seg async for seg in pipe_1.get_segments()]
            await pipe_1.close()

            # Pipeline 2
            stt_2 = MockSTT(segments=_make_segments(mid_2, n=1))
            pipe_2 = AudioPipeline(
                stt_provider=stt_2,
                event_publisher=publisher,
                meeting_id=mid_2,
            )
            await pipe_2.process_audio(b"\x80" * 10)
            _ = [seg async for seg in pipe_2.get_segments()]
            await pipe_2.close()

            entries = await redis_client.xrange(STREAM_KEY)
            # 3 events per pipeline (started, segment, ended) = 6 total
            assert len(entries) == 6

            # Extract meeting IDs from all events
            meeting_ids = set()
            for entry in entries:
                payload = json.loads(entry[1]["payload"])
                meeting_ids.add(payload["meeting_id"])

            assert str(mid_1) in meeting_ids
            assert str(mid_2) in meeting_ids
        finally:
            await publisher.close()
