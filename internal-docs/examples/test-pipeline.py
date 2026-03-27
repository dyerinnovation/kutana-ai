#!/usr/bin/env python3
"""End-to-end pipeline test: publish fake transcript segments to Redis,
watch for extraction results on the insights pub/sub channel.

Tests the full flow without needing audio or Deepgram:
  transcript segments → task-engine windowing → LLM extraction → insights published

Usage:
    # Against local services (default)
    python examples/test-pipeline.py

    # Against Docker Compose stack
    REDIS_URL=redis://localhost:6379/0 python examples/test-pipeline.py

Requirements:
    pip install redis  (or: uv run python examples/test-pipeline.py)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime

import redis.asyncio as redis_async

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
STREAM_KEY = "convene:events"
TIMEOUT_SECONDS = 90  # Wait up to 90s for LLM to respond (window is 30s by default)

# Fake meeting transcript — rich with actionable content so the extractor fires
MEETING_ID = str(uuid.uuid4())
SEGMENTS = [
    ("Alice", "Good morning everyone. Let's kick off the Q2 planning meeting."),
    ("Bob", "Thanks Alice. I'll own the backend API refactor and have it done by end of next week."),
    ("Alice", "Perfect. We also decided to sunset the legacy v1 endpoints on April 30th."),
    ("Carol", "I'll take the frontend migration tasks. Should be done by April 15th."),
    ("Bob", "We need to make sure the database migration runs before we flip the feature flag."),
    ("Alice", "Agreed. That's a blocker. Bob, can you also write the migration guide?"),
    ("Bob", "Yes, I'll add that to my list. Target is April 10th."),
    ("Carol", "I'll set up the staging environment for testing by April 5th."),
    ("Alice", "Great. Key decision: we're going with PostgreSQL 16 for the new schema."),
    ("Bob", "One more thing — we need to update the security audit docs before the April 30th launch."),
    ("Alice", "I'll handle that. Let's wrap up. Thanks everyone."),
]


def _make_segment_payload(
    meeting_id: str,
    speaker: str,
    text: str,
    start_time: float,
    end_time: float,
) -> dict[str, str]:
    """Build the Redis stream fields for a transcript.segment.final event."""
    segment_id = str(uuid.uuid4())
    now = datetime.now(tz=UTC).isoformat()

    event = {
        "event_type": "transcript.segment.final",
        "meeting_id": meeting_id,
        "segment": {
            "id": segment_id,
            "meeting_id": meeting_id,
            "speaker_id": speaker,
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
            "confidence": 0.95,
            "created_at": now,
        },
    }
    return {
        "event_type": "transcript.segment.final",
        "payload": json.dumps(event, default=str),
    }


async def publish_segments(r: redis_async.Redis, meeting_id: str) -> None:
    """Push all fake transcript segments to the Redis stream."""
    print(f"Publishing {len(SEGMENTS)} segments for meeting {meeting_id} ...")
    t = 0.0
    for speaker, text in SEGMENTS:
        duration = 0.5 + len(text) * 0.05  # rough duration estimate
        fields = _make_segment_payload(meeting_id, speaker, text, t, t + duration)
        entry_id = await r.xadd(STREAM_KEY, fields)
        print(f"  [{entry_id}] {speaker}: {text[:60]}")
        t += duration
        await asyncio.sleep(0.05)  # small delay to avoid burst


async def wait_for_insights(
    r: redis_async.Redis,
    meeting_id: str,
    timeout: float,
) -> dict | None:
    """Subscribe to the meeting insights channel and wait for results."""
    channel = f"meeting.{meeting_id}.insights"
    print(f"\nListening on pub/sub channel: {channel}")
    print(f"(Waiting up to {timeout}s for task-engine to process...)\n")

    pubsub = r.pubsub()
    await pubsub.subscribe(channel)

    deadline = asyncio.get_event_loop().time() + timeout
    try:
        while asyncio.get_event_loop().time() < deadline:
            remaining = deadline - asyncio.get_event_loop().time()
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=min(5.0, remaining),
            )
            if message and message["type"] == "message":
                return json.loads(message["data"])
            await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

    return None


def print_result(result: dict) -> None:
    """Pretty-print the extraction result."""
    entities = result.get("entities", [])
    print(f"SUCCESS — received {len(entities)} extracted entities:\n")
    for e in entities:
        etype = e.get("entity_type", "?")
        # Show the most informative field depending on entity type
        label = (
            e.get("title")
            or e.get("text")
            or e.get("description")
            or e.get("content")
            or str(e.get("id", ""))[:8]
        )
        assignee = e.get("assignee") or e.get("owner") or ""
        due = e.get("due_date") or e.get("deadline") or ""
        parts = [f"[{etype}] {label}"]
        if assignee:
            parts.append(f"  assignee: {assignee}")
        if due:
            parts.append(f"  due: {due}")
        print("\n".join(parts))
    print(f"\nbatch_id: {result.get('batch_id')}")
    print(f"processing_time_ms: {result.get('processing_time_ms')}")


async def main() -> int:
    print("=== Convene AI Pipeline Test ===")
    print(f"Redis: {REDIS_URL}")
    print(f"Meeting ID: {MEETING_ID}\n")

    r: redis_async.Redis = redis_async.from_url(REDIS_URL, decode_responses=True)
    try:
        await r.ping()
    except Exception as exc:
        print(f"ERROR: Cannot connect to Redis at {REDIS_URL}: {exc}")
        print("Make sure Redis is running: docker compose up redis")
        return 1

    # Subscribe before publishing so we don't miss the message
    pubsub_task = asyncio.create_task(
        wait_for_insights(r, MEETING_ID, TIMEOUT_SECONDS)
    )
    # Small delay to let subscribe complete before publishing
    await asyncio.sleep(0.3)

    await publish_segments(r, MEETING_ID)
    print("\nAll segments published. Waiting for task-engine to extract entities...")
    print("(The task-engine uses a 30s window, so results arrive ~30s after publish)\n")

    result = await pubsub_task

    await r.aclose()

    if result is None:
        print("TIMEOUT — no insights received within the timeout window.")
        print("\nPossible causes:")
        print("  • task-engine is not running: docker compose up task-engine")
        print("  • ANTHROPIC_API_KEY is not set in .env")
        print("  • task-engine window hasn't fired yet (default: 30s)")
        return 1

    print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
