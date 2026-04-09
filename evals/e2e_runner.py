"""E2E eval runner: create meeting -> activate agent -> observe MCP calls.

Runs against the live dev cluster, creating a real meeting, activating
a managed agent, injecting transcript segments, and observing the
agent's actual MCP tool calls via Redis event stream.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import aiohttp
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api-dev.kutana.ai/v1"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
EVENT_STREAM_KEY = "kutana:events"


class E2ERunner:
    """End-to-end eval runner against the live dev cluster.

    Args:
        api_base: Base URL for the Kutana API.
        auth_token: JWT bearer token for API authentication.
        redis_url: Redis URL for observing agent events.
    """

    def __init__(
        self,
        api_base: str = DEFAULT_API_BASE,
        auth_token: str = "",
        redis_url: str = DEFAULT_REDIS_URL,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._auth_token = auth_token
        self._redis_url = redis_url
        self._session: aiohttp.ClientSession | None = None
        self._redis: aioredis.Redis[str] | None = None

    async def __aenter__(self) -> E2ERunner:
        """Set up HTTP and Redis connections."""
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._auth_token}"},
        )
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Tear down connections."""
        if self._session:
            await self._session.close()
        if self._redis:
            await self._redis.aclose()

    async def create_meeting(self, title: str) -> UUID:
        """Create a meeting on the dev cluster.

        Args:
            title: Meeting title.

        Returns:
            The created meeting's UUID.
        """
        assert self._session is not None
        async with self._session.post(
            f"{self._api_base}/meetings",
            json={"title": title},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return UUID(data["id"])

    async def activate_agent(
        self,
        meeting_id: UUID,
        template_name: str,
    ) -> str:
        """Activate a managed agent for a meeting.

        Args:
            meeting_id: Meeting to activate the agent in.
            template_name: Agent template name.

        Returns:
            The hosted agent session ID.
        """
        assert self._session is not None
        async with self._session.post(
            f"{self._api_base}/meetings/{meeting_id}/agents",
            json={"template_name": template_name},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["session_id"]

    async def start_meeting(self, meeting_id: UUID) -> None:
        """Start a meeting (triggers meeting.started event).

        Args:
            meeting_id: Meeting to start.
        """
        assert self._session is not None
        async with self._session.post(
            f"{self._api_base}/meetings/{meeting_id}/start",
        ) as resp:
            resp.raise_for_status()

    async def inject_transcript(
        self,
        meeting_id: UUID,
        segments: list[dict[str, Any]],
    ) -> None:
        """Inject synthetic transcript segments into Redis stream.

        Simulates the audio pipeline producing transcript.segment.final
        events for the given meeting.

        Args:
            meeting_id: Target meeting.
            segments: List of dicts with speaker, text, start_time keys.
        """
        assert self._redis is not None
        for seg in segments:
            payload = json.dumps(
                {
                    "meeting_id": str(meeting_id),
                    "segment": {
                        "meeting_id": str(meeting_id),
                        "speaker_name": seg.get("speaker", "Unknown"),
                        "text": seg.get("text", ""),
                        "start_time": seg.get("timestamp_seconds", 0.0),
                    },
                }
            )
            await self._redis.xadd(
                EVENT_STREAM_KEY,
                {"event_type": "transcript.segment.final", "payload": payload},
                maxlen=10_000,
                approximate=True,
            )

    async def observe_agent_events(
        self,
        meeting_id: UUID,
        timeout: float = 60.0,
        max_events: int = 50,
    ) -> list[dict[str, Any]]:
        """Observe agent events from Redis stream for a meeting.

        Polls the kutana:events stream for events matching the given
        meeting_id until timeout or max_events reached.

        Args:
            meeting_id: Meeting to observe events for.
            timeout: Maximum seconds to observe.
            max_events: Stop after collecting this many events.

        Returns:
            List of event dicts with event_type and payload.
        """
        assert self._redis is not None
        events: list[dict[str, Any]] = []
        meeting_id_str = str(meeting_id)
        deadline = asyncio.get_event_loop().time() + timeout
        last_id = "$"

        while asyncio.get_event_loop().time() < deadline and len(events) < max_events:
            remaining = deadline - asyncio.get_event_loop().time()
            block_ms = int(min(remaining * 1000, 2000))
            if block_ms <= 0:
                break

            response = await self._redis.xread(
                streams={EVENT_STREAM_KEY: last_id},
                count=10,
                block=block_ms,
            )

            if not response:
                continue

            for _stream_name, entries in response:
                for entry_id, fields in entries:
                    last_id = entry_id
                    raw_payload = fields.get("payload", "")
                    try:
                        payload = json.loads(raw_payload)
                    except json.JSONDecodeError:
                        continue

                    if payload.get("meeting_id") == meeting_id_str:
                        events.append(
                            {
                                "event_type": fields.get("event_type", ""),
                                "payload": payload,
                            }
                        )

        return events

    async def end_meeting(self, meeting_id: UUID) -> None:
        """End a meeting (triggers meeting.ended event).

        Args:
            meeting_id: Meeting to end.
        """
        assert self._session is not None
        async with self._session.post(
            f"{self._api_base}/meetings/{meeting_id}/end",
        ) as resp:
            resp.raise_for_status()

    async def cleanup_meeting(self, meeting_id: UUID) -> None:
        """Delete a meeting after eval completes.

        Args:
            meeting_id: Meeting to clean up.
        """
        assert self._session is not None
        async with self._session.delete(
            f"{self._api_base}/meetings/{meeting_id}",
        ) as resp:
            if resp.status not in (200, 204, 404):
                logger.warning("Failed to clean up meeting %s: %s", meeting_id, resp.status)
