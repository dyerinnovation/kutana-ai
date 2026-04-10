"""E2E eval runner: create meeting -> activate agent -> observe MCP calls.

Runs against the live dev cluster, creating a real meeting, activating
a managed agent, injecting transcript segments, and observing the
agent's actual MCP tool calls via Redis event stream.

**API mode** — uses the Kutana API for agent activation and observes
events from the Redis stream. Exercises the full Kutana pipeline (audio service
→ Redis → agent_lifecycle consumer → Anthropic → Redis → eval observer).
"""

from __future__ import annotations

import asyncio
import dataclasses
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


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class E2EResult:
    """Structured result from a complete E2E eval run.

    Attributes:
        meeting_id: UUID of the Kutana meeting created for this eval.
        session_id: Kutana hosted session ID.
        agent_messages: Ordered list of text strings from ``agent.message``
            events. The last entry is the meeting summary (after ``end_meeting``).
        tool_calls: All tool invocations: ``agent.mcp_tool_use`` and
            ``agent.custom_tool_use`` events, each as
            ``{"type": ..., "tool_name": ..., "input": ...}``.
        mcp_tool_results: Not populated in API mode (the pipeline does not
            forward these to Redis). Retained for result schema compatibility.
        summary_text: The agent's final response after the meeting ended.
            Extracted from the last ``agent.message`` in the timeline.
        errors: Error strings from ``session.error`` events.
        event_timeline: Full ordered list of all captured events, each with at
            least a ``"type"`` key plus type-specific payload fields.
    """

    meeting_id: UUID
    session_id: str
    agent_messages: list[str] = dataclasses.field(default_factory=list)
    tool_calls: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    mcp_tool_results: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    summary_text: str = ""
    errors: list[str] = dataclasses.field(default_factory=list)
    event_timeline: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    @property
    def passed_smoke_test(self) -> bool:
        """True if no errors and the agent produced at least one response."""
        return not self.errors and bool(self.agent_messages or self.summary_text)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _collect_redis_event(ev: dict[str, Any], result: E2EResult) -> None:
    """Extract data from a Redis stream event dict into ``result``.

    Redis events carry only the subset forwarded by the Kutana pipeline.
    MCP tool results are not available here.

    Args:
        ev: Dict with ``event_type`` and ``payload`` keys from
            ``observe_agent_events``.
        result: E2EResult to accumulate into.
    """
    event_type: str = ev.get("event_type", "")
    payload: dict[str, Any] = ev.get("payload", {})
    entry: dict[str, Any] = {"type": event_type, **payload}

    if event_type == "agent.message":
        content = str(payload.get("content", ""))
        result.agent_messages.append(content)

    elif event_type in ("agent.mcp_tool_use", "agent.custom_tool_use"):
        result.tool_calls.append(
            {
                "type": event_type,
                "tool_name": payload.get("tool_name", "unknown"),
                "input": {},
            }
        )

    elif event_type == "session.error":
        result.errors.append(str(payload.get("message", "Unknown error")))

    result.event_timeline.append(entry)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class E2ERunner:
    """End-to-end eval runner against the live dev cluster.

    Args:
        api_base: Base URL for the Kutana API.
        auth_token: Bearer token (JWT or API key) for API authentication.
            Used for meeting/transcript endpoints (CurrentUserOrAgent).
        login_email: Optional email to exchange for a JWT via POST /auth/login.
            Required for endpoints that need CurrentUser (e.g. agent-templates activate).
        login_password: Password paired with login_email.
        redis_url: Redis URL for observing agent events.
        model: Unused — kept for interface compatibility.
    """

    def __init__(
        self,
        api_base: str = DEFAULT_API_BASE,
        auth_token: str = "",
        redis_url: str = DEFAULT_REDIS_URL,
        model: str = "",
        login_email: str = "",
        login_password: str = "",
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._auth_token = auth_token
        self._redis_url = redis_url
        self._model = model
        self._login_email = login_email
        self._login_password = login_password
        self._jwt_token: str = ""  # obtained via login if email/password provided
        self._session: aiohttp.ClientSession | None = None
        self._redis: aioredis.Redis[str] | None = None

    async def __aenter__(self) -> E2ERunner:
        """Set up HTTP and Redis connections; optionally log in to get a JWT."""
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._auth_token}"},
        )
        # Exchange email/password for a JWT if credentials provided.
        # Required for endpoints that use CurrentUser (JWT-only) such as
        # POST /agent-templates/{id}/activate.
        if self._login_email and self._login_password:
            async with self._session.post(
                f"{self._api_base}/auth/login",
                json={"email": self._login_email, "password": self._login_password},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                self._jwt_token = data["access_token"]
            logger.info("Logged in as %s, obtained JWT", self._login_email)
        else:
            # Fall back to using auth_token as the JWT (works if it IS a JWT)
            self._jwt_token = self._auth_token

        self._redis = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
            socket_keepalive=True,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        """Tear down connections."""
        if self._session:
            await self._session.close()
        if self._redis:
            await self._redis.aclose()

    # -----------------------------------------------------------------------
    # Kutana API methods
    # -----------------------------------------------------------------------

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
        model: str | None = None,
    ) -> str:
        """Activate a managed agent for a meeting.

        Looks up the template by name, then calls
        POST /agent-templates/{template_id}/activate.

        Args:
            meeting_id: Meeting to activate the agent in.
            template_name: Agent template name (e.g. "Meeting Notetaker").
            model: Ignored — the activate endpoint does not accept a model
                override; tier-based model selection happens server-side.

        Returns:
            The hosted agent session ID.
        """
        assert self._session is not None

        # Resolve template name → template_id (uses general session; list is public).
        async with self._session.get(
            f"{self._api_base}/agent-templates",
        ) as resp:
            resp.raise_for_status()
            templates: list[dict[str, Any]] = await resp.json()

        template_id: str | None = None
        for t in templates:
            if t.get("name", "").lower() == template_name.lower():
                template_id = t["id"]
                break

        if template_id is None:
            raise ValueError(
                f"No agent template found with name '{template_name}'. "
                f"Available: {[t.get('name') for t in templates]}"
            )

        # The activate endpoint uses CurrentUser (JWT only), so send the JWT
        # obtained during login, not the API key used for other calls.
        jwt_headers = {"Authorization": f"Bearer {self._jwt_token}"}
        async with self._session.post(
            f"{self._api_base}/agent-templates/{template_id}/activate",
            json={"meeting_id": str(meeting_id)},
            headers=jwt_headers,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["id"]

    async def start_meeting(self, meeting_id: UUID) -> None:
        """Start a meeting (triggers meeting.started event in the pipeline).

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
        delay: float = 1.0,
    ) -> None:
        """Inject synthetic transcript segments into the Redis event stream.

        Publishes each ``transcript.segment.final`` event individually with a
        configurable delay between them. The delay simulates real-time speech
        and allows the Kutana pipeline consumer to process each segment before
        the next arrives — testing incremental state accumulation.

        Args:
            meeting_id: Target meeting.
            segments: List of dicts with ``speaker``, ``text``, and
                ``timestamp_seconds`` keys.
            delay: Seconds to sleep between consecutive segment publishes.
                Use 0 to disable delays (bulk injection).
        """
        assert self._redis is not None
        for i, seg in enumerate(segments):
            if i > 0 and delay > 0:
                # Use start_time delta if available, capped at 3 s for eval speed.
                if i >= 1:
                    prev_ts = float(segments[i - 1].get("timestamp_seconds", 0.0))
                    curr_ts = float(seg.get("timestamp_seconds", 0.0))
                    delta = max(0.0, curr_ts - prev_ts)
                    actual_delay = min(delta, 3.0) if delta > 0 else delay
                else:
                    actual_delay = delay
                await asyncio.sleep(actual_delay)

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
            logger.debug(
                "Injected segment %d/%d for meeting %s: %s",
                i + 1,
                len(segments),
                meeting_id,
                seg.get("text", "")[:60],
            )

    async def observe_agent_events(
        self,
        meeting_id: UUID,
        timeout: float = 60.0,
        max_events: int = 200,
        stop_on_n_idle: int = 0,
    ) -> list[dict[str, Any]]:
        """Observe agent events from the Redis stream for a meeting.

        Polls ``kutana:events`` for entries matching ``meeting_id``. Captures
        all event types forwarded by the Kutana pipeline:
        - ``agent.message`` — agent text responses
        - ``agent.mcp_tool_use`` — MCP tool invocations
        - ``agent.custom_tool_use`` — custom tool invocations
        - ``session.error`` — session error events
        - ``session.status_idle`` — agent finished current task

        Args:
            meeting_id: Meeting to observe events for.
            timeout: Maximum seconds to observe before returning.
            max_events: Stop after collecting this many matching events.
            stop_on_n_idle: If > 0, stop after seeing this many
                ``session.status_idle`` events. Use 2 in ``run_e2e_eval`` to
                capture both the in-meeting idle and the post-summary idle.

        Returns:
            Ordered list of event dicts, each with ``event_type`` and
            ``payload`` keys.
        """
        assert self._redis is not None
        events: list[dict[str, Any]] = []
        meeting_id_str = str(meeting_id)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        last_id = "$"
        idle_count = 0

        while loop.time() < deadline and len(events) < max_events:
            remaining = deadline - loop.time()
            block_ms = int(min(remaining * 1000, 2000))
            if block_ms <= 0:
                break

            try:
                response = await self._redis.xread(
                    streams={EVENT_STREAM_KEY: last_id},
                    count=20,
                    block=block_ms,
                )
            except Exception as exc:
                logger.warning("Redis xread error (will retry): %s", exc)
                await asyncio.sleep(0.5)
                continue

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

                    if payload.get("meeting_id") != meeting_id_str:
                        continue

                    event_type = fields.get("event_type", "")
                    events.append({"event_type": event_type, "payload": payload})
                    logger.debug("Observed %s for meeting %s", event_type, meeting_id)

                    if stop_on_n_idle and event_type == "session.status_idle":
                        idle_count += 1
                        if idle_count >= stop_on_n_idle:
                            return events

                    if len(events) >= max_events:
                        return events

        return events

    async def end_meeting(self, meeting_id: UUID) -> None:
        """End a meeting (triggers summary request to all active agents).

        Args:
            meeting_id: Meeting to end.
        """
        assert self._session is not None
        async with self._session.post(
            f"{self._api_base}/meetings/{meeting_id}/end",
        ) as resp:
            resp.raise_for_status()

    async def cleanup_meeting(self, meeting_id: UUID) -> None:
        """No-op — meetings persist after evals; end_meeting already marks them completed.

        The Kutana API has no DELETE /meetings endpoint, so cleanup is a no-op.

        Args:
            meeting_id: Meeting ID (unused).
        """
        logger.debug("Skipping meeting cleanup for %s — no DELETE endpoint", meeting_id)

    # -----------------------------------------------------------------------
    # Orchestrator
    # -----------------------------------------------------------------------

    async def run_e2e_eval(
        self,
        title: str,
        template_name: str,
        segments: list[dict[str, Any]],
        participants: list[str] | None = None,
        segment_delay: float = 1.0,
        observe_timeout: float = 120.0,
        max_events: int = 200,
        model: str | None = None,
    ) -> E2EResult:
        """Run a complete managed-agent eval lifecycle end-to-end.

        Full lifecycle:
          create_meeting → activate_agent → start_meeting →
          inject segments (individually, with timing gaps) →
          observe all agent event types →
          end_meeting → capture summary → cleanup

        Args:
            title: Meeting title.
            template_name: Agent template name (e.g. ``"Meeting Notetaker"``).
            segments: Synthetic transcript segments, each a dict with
                ``speaker``, ``text``, and ``timestamp_seconds`` keys.
            participants: Display names for the meeting context header.
                Defaults to extracting unique speakers from ``segments``.
            segment_delay: Base delay (seconds) between segment injections.
                The actual delay is ``min(timestamp_delta, 3.0)`` or this
                value if no delta is available.
            observe_timeout: Total seconds to wait for agent events.
                Should cover injection time + Anthropic round-trips + summary.
            max_events: Maximum Redis events to collect.
            model: Optional model override passed to the cluster API when
                activating the agent (e.g. ``"claude-haiku-4-5-20251001"``
                for cheap smoke tests).

        Returns:
            Structured :class:`E2EResult` with all agent messages, tool calls,
            summary text, errors, and the full event timeline.
        """
        if participants is None:
            seen: dict[str, None] = {}
            for seg in segments:
                seen[seg.get("speaker", "Unknown")] = None
            participants = list(seen)

        meeting_id = await self.create_meeting(title)
        result = E2EResult(meeting_id=meeting_id, session_id="")

        try:
            await self._run_api_mode(
                meeting_id=meeting_id,
                template_name=template_name,
                segments=segments,
                segment_delay=segment_delay,
                observe_timeout=observe_timeout,
                max_events=max_events,
                result=result,
                model=model,
            )
        finally:
            await self.cleanup_meeting(meeting_id)

        return result

    # -----------------------------------------------------------------------
    # Internal: API mode
    # -----------------------------------------------------------------------

    async def _run_api_mode(
        self,
        meeting_id: UUID,
        template_name: str,
        segments: list[dict[str, Any]],
        segment_delay: float,
        observe_timeout: float,
        max_events: int,
        result: E2EResult,
        model: str | None = None,
    ) -> None:
        """API-mode eval: Kutana pipeline + Redis observation.

        Starts observation before injection so no events are missed.
        The observer runs concurrently with injection and end_meeting.
        Uses ``stop_on_n_idle=2`` to capture both the in-meeting idle
        and the post-summary idle without hanging until full timeout.

        Args:
            meeting_id: Pre-created meeting UUID.
            template_name: Agent template name.
            segments: Transcript segments.
            segment_delay: Delay between segment injections.
            observe_timeout: Observation timeout in seconds.
            max_events: Max events to collect.
            result: E2EResult to populate (mutated in place).
            model: Optional model override passed to activate_agent.
        """
        # Start the observation task FIRST so it catches all pipeline events.
        obs_task: asyncio.Task[list[dict[str, Any]]] = asyncio.create_task(
            self.observe_agent_events(
                meeting_id,
                timeout=observe_timeout,
                max_events=max_events,
                stop_on_n_idle=2,
            )
        )
        # Yield to let the observation task enter its xread loop.
        await asyncio.sleep(0.2)

        # Activate agent and start meeting.
        session_id = await self.activate_agent(meeting_id, template_name, model=model)
        result.session_id = session_id
        await self.start_meeting(meeting_id)
        logger.info(
            "API mode: meeting %s started, session %s activated",
            meeting_id,
            session_id,
        )

        # Inject transcript segments with timing gaps.
        await self.inject_transcript(meeting_id, segments, delay=segment_delay)
        logger.info("Injected %d segments for meeting %s", len(segments), meeting_id)

        # Allow the pipeline to process the last segment before ending.
        await asyncio.sleep(3.0)

        # End meeting — triggers summary request in agent_lifecycle.
        await self.end_meeting(meeting_id)
        logger.info("Ended meeting %s, waiting for summary events", meeting_id)

        # Wait for observation to capture summary idle (or timeout).
        try:
            raw_events = await asyncio.wait_for(obs_task, timeout=observe_timeout)
        except TimeoutError:
            logger.warning("Observation timed out for meeting %s", meeting_id)
            raw_events = []

        # Parse raw Redis events into result fields.
        for ev in raw_events:
            _collect_redis_event(ev, result)

        # The last agent.message is the summary.
        if result.agent_messages:
            result.summary_text = result.agent_messages[-1]
