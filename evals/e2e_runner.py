"""E2E eval runner: create meeting -> select agents -> start -> observe MCP calls.

Runs against the live dev cluster, creating a real meeting, selecting
managed-agent templates, starting the meeting (which fires background
warming), injecting transcript segments, and observing the agent's
actual MCP tool calls via the Redis event stream.

**Phase A.7 decoupled flow**:
1. ``POST /v1/meetings`` — create meeting
2. ``PUT /v1/meetings/{id}/selected-agents`` — snapshot the desired
   template list
3. ``SADD kutana:presence:{meeting_id} eval-participant`` — drive
   presence so ``PresenceReconciler`` does not reap the warmed sessions
4. ``POST /v1/meetings/{id}/start`` — transitions to ACTIVE and fires
   one background ``_warm_agent_in_background`` per selection
5. Observer waits for ``agent.session.warmed`` before injecting
   transcripts so the managed agent session is ready to receive them
6. Inject transcript segments via Redis, observe events, end meeting
7. ``SREM`` the presence entry so the reconciler cleans up any stragglers

The old ``/v1/agent-templates/{id}/activate`` path is deprecated and is
no longer called from here.
"""

from __future__ import annotations

import asyncio
import contextlib
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
PRESENCE_KEY_PREFIX = "kutana:presence:"
# Stable synthetic participant ID used to drive presence for evals. The
# real agent-gateway would publish participant.joined events which the
# api-server PresenceMaterializer then materializes into the same set —
# we skip the gateway hop and write directly to the materialized set.
EVAL_PARTICIPANT_ID = "eval-stub-participant"


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
            Required for endpoints that need CurrentUser (e.g. PUT /meetings/{id}/selected-agents).
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
        # PUT /meetings/{id}/selected-agents.
        if self._login_email and self._login_password:
            async with self._session.post(
                f"{self._api_base}/auth/login",
                json={"email": self._login_email, "password": self._login_password},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                self._jwt_token = data["token"]
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

    async def _resolve_template_id(self, template_name: str) -> str:
        """Resolve a template name to a template UUID via GET /agent-templates.

        Args:
            template_name: Case-insensitive template name.

        Returns:
            Template UUID as a string.

        Raises:
            ValueError: If no template with that name exists.
        """
        assert self._session is not None
        async with self._session.get(
            f"{self._api_base}/agent-templates",
        ) as resp:
            resp.raise_for_status()
            templates: list[dict[str, Any]] = await resp.json()

        for t in templates:
            if t.get("name", "").lower() == template_name.lower():
                return str(t["id"])

        raise ValueError(
            f"No agent template found with name '{template_name}'. "
            f"Available: {[t.get('name') for t in templates]}"
        )

    async def set_selected_agents(
        self,
        meeting_id: UUID,
        template_names: list[str],
    ) -> list[str]:
        """Snapshot the desired managed-agent templates on the meeting.

        Calls ``PUT /v1/meetings/{meeting_id}/selected-agents`` with the
        resolved template IDs. The endpoint fully replaces any existing
        selection — rows not present in the body are deleted.

        This is the Phase A.7 replacement for the deprecated
        ``/v1/agent-templates/{id}/activate`` path. Actual agent warming
        is deferred until ``start_meeting`` fires background tasks.

        Args:
            meeting_id: Meeting to attach selections to.
            template_names: Ordered list of agent template names.

        Returns:
            The resolved template UUIDs in the same order.
        """
        assert self._session is not None
        template_ids = [await self._resolve_template_id(name) for name in template_names]

        body = {
            "selections": [
                {"template_id": tid, "system_prompt_override": None, "sop_id": None}
                for tid in template_ids
            ]
        }
        # PUT /selected-agents uses CurrentUser (JWT only).
        jwt_headers = {"Authorization": f"Bearer {self._jwt_token}"}
        async with self._session.put(
            f"{self._api_base}/meetings/{meeting_id}/selected-agents",
            json=body,
            headers=jwt_headers,
        ) as resp:
            resp.raise_for_status()
            await resp.json()
        return template_ids

    async def mark_presence(self, meeting_id: UUID) -> None:
        """Drive synthetic presence for a meeting via the Redis set.

        ``SADD kutana:presence:{meeting_id} eval-stub-participant``.

        The ``PresenceReconciler`` in api-server watches this set every
        30 seconds. Without at least one member it will shut down any
        active managed-agent sessions for the meeting, so evals must
        call this before ``start_meeting`` (or immediately after) and
        keep the entry in place until the meeting ends.

        Args:
            meeting_id: Meeting whose presence set to populate.
        """
        assert self._redis is not None
        await self._redis.sadd(
            f"{PRESENCE_KEY_PREFIX}{meeting_id}",
            EVAL_PARTICIPANT_ID,
        )
        logger.info("Presence SADD kutana:presence:%s", meeting_id)

    async def clear_presence(self, meeting_id: UUID) -> None:
        """Remove the synthetic presence entry for a meeting.

        Called during cleanup so the reconciler does not keep the meeting
        warm after the eval has ended. A no-op if the entry is already
        absent.

        Args:
            meeting_id: Meeting whose presence set to drain.
        """
        assert self._redis is not None
        await self._redis.srem(
            f"{PRESENCE_KEY_PREFIX}{meeting_id}",
            EVAL_PARTICIPANT_ID,
        )
        logger.debug("Presence SREM kutana:presence:%s", meeting_id)

    async def wait_for_agent_warmed(
        self,
        meeting_id: UUID,
        timeout: float = 90.0,
    ) -> str | None:
        """Block until at least one ``agent.session.warmed`` event for the meeting.

        After ``start_meeting`` the api-server fires background warming
        tasks that take 5-30 s each. This helper reads the shared event
        stream until the first warmed event for our meeting_id arrives
        and returns its ``hosted_session_id``. Returns ``None`` on timeout.

        Args:
            meeting_id: Meeting to wait on.
            timeout: Maximum seconds to block.

        Returns:
            The ``hosted_session_id`` from the first warmed event, or
            ``None`` if the timeout elapsed.
        """
        assert self._redis is not None
        meeting_id_str = str(meeting_id)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        last_id = "$"

        while loop.time() < deadline:
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
                    event_type = fields.get("event_type", "")
                    if event_type not in (
                        "agent.session.warmed",
                        "agent.session.failed",
                    ):
                        continue
                    try:
                        payload = json.loads(fields.get("payload", ""))
                    except json.JSONDecodeError:
                        continue
                    if payload.get("meeting_id") != meeting_id_str:
                        continue
                    if event_type == "agent.session.failed":
                        raise RuntimeError(
                            f"Agent warming failed: {payload.get('error', 'unknown')}"
                        )
                    hosted_session_id = payload.get("hosted_session_id")
                    logger.info(
                        "Agent warmed for meeting %s (hosted_session_id=%s)",
                        meeting_id,
                        hosted_session_id,
                    )
                    return str(hosted_session_id) if hosted_session_id else ""
        logger.warning("Timed out waiting for agent.session.warmed for meeting %s", meeting_id)
        return None

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
        """Drain synthetic presence and leave the meeting row in place.

        The Kutana API has no DELETE /meetings endpoint, so the row
        persists as a completed meeting. We only need to remove the
        eval's SADD entry so the presence reconciler does not keep the
        meeting marked as populated after the eval exits.

        Args:
            meeting_id: Meeting whose presence entry to drain.
        """
        with contextlib.suppress(Exception):
            await self.clear_presence(meeting_id)
        logger.debug("Meeting %s cleanup complete — no DELETE endpoint", meeting_id)

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

        Full lifecycle (Phase A.7 decoupled):
          create_meeting → set_selected_agents → mark_presence →
          start_meeting → wait_for_agent_warmed →
          inject segments (individually, with timing gaps) →
          observe all agent event types →
          end_meeting → capture summary → cleanup (clears presence)

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
        """API-mode eval: Phase A.7 decoupled lifecycle + Redis observation.

        Order of operations:
        1. Start the observation task so it catches every pipeline event.
        2. PUT /selected-agents snapshotting the template list.
        3. SADD the presence set so the reconciler does not reap warms.
        4. POST /start — fires background warming.
        5. Wait for the first ``agent.session.warmed`` event so the
           managed-agent session is ready to receive transcripts. (If the
           warm fails we raise and let the cleanup path drain presence.)
        6. Inject transcripts, end meeting, collect observations.

        Args:
            meeting_id: Pre-created meeting UUID.
            template_name: Agent template name.
            segments: Transcript segments.
            segment_delay: Delay between segment injections.
            observe_timeout: Observation timeout in seconds.
            max_events: Max events to collect.
            result: E2EResult to populate (mutated in place).
            model: Unused — tier-based selection happens server-side.
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

        # Snapshot the desired template list on the meeting row.
        await self.set_selected_agents(meeting_id, [template_name])

        # Drive presence BEFORE starting so the PresenceReconciler does
        # not race the start handler and reap in-flight warms.
        await self.mark_presence(meeting_id)

        # Start the meeting — this fires one background warm per selection.
        await self.start_meeting(meeting_id)
        logger.info("API mode: meeting %s started, waiting for warmed event", meeting_id)

        # Block until the first warmed event arrives so the managed agent
        # session is actually ready to accept user.message segments.
        hosted_session_id = await self.wait_for_agent_warmed(
            meeting_id, timeout=min(observe_timeout, 120.0)
        )
        if hosted_session_id is None:
            logger.warning(
                "No agent.session.warmed observed for meeting %s within timeout — "
                "proceeding anyway; segments may be dropped",
                meeting_id,
            )
        else:
            result.session_id = hosted_session_id

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
