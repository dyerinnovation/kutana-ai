"""Async HTTP client for the Kutana API server.

Uses aiohttp (NOT httpx) for mDNS compatibility with the DGX Spark cluster.
All I/O is async; click commands bridge via ``asyncio.run()``.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import aiohttp

from kutana_cli.config import load_config, save_config

logger = logging.getLogger(__name__)


class KutanaClient:
    """Async HTTP client for the Kutana API.

    Handles token exchange (API key -> gateway JWT) and wraps common
    endpoints used by the CLI. Auto-authenticates on the first request
    if no valid token is cached.

    Attributes:
        base_url: API server base URL (e.g. ``https://dev.kutana.ai/api``).
        api_key: Agent API key.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._jwt_token: str | None = None
        self._jwt_expires_at: float = 0

        # Try to load cached JWT from config
        config = load_config()
        cached_jwt = config.get("jwt_token")
        cached_exp = config.get("jwt_expires_at", 0)
        if cached_jwt and cached_exp > time.time():
            self._jwt_token = cached_jwt
            self._jwt_expires_at = cached_exp

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> dict[str, Any]:
        """Exchange the API key for a short-lived gateway JWT.

        Caches the JWT in memory and in ``~/.kutana/config.json``.

        Returns:
            Response dict with ``token``, ``agent_config_id``, ``name``.

        Raises:
            RuntimeError: If the token exchange fails.
        """
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.base_url}/v1/token/gateway",
                headers={"X-API-Key": self.api_key},
            ) as resp,
        ):
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Authentication failed ({resp.status}): {text}")
            data: dict[str, Any] = await resp.json()
            self._jwt_token = data["token"]
            # Gateway tokens are valid for 1 hour; cache with 5 min buffer
            self._jwt_expires_at = time.time() + 3300

            # Persist to config
            config = load_config()
            config["jwt_token"] = self._jwt_token
            config["jwt_expires_at"] = self._jwt_expires_at
            save_config(config)

            return data

    async def _ensure_auth(self) -> None:
        """Auto-authenticate if no valid token is cached."""
        if self._jwt_token is None or time.time() >= self._jwt_expires_at:
            await self.authenticate()

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Return Bearer auth headers using the current JWT."""
        if self._jwt_token:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        return {"X-API-Key": self.api_key}

    # ------------------------------------------------------------------
    # Generic request helper
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Send an authenticated HTTP request to the API server.

        Auto-authenticates on first call if needed.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE).
            path: API path (e.g. ``/v1/meetings``).
            json_body: Optional JSON request body.
            params: Optional query parameters.

        Returns:
            Parsed JSON response, or None for 204.

        Raises:
            RuntimeError: If the request fails with a 4xx/5xx status.
        """
        await self._ensure_auth()
        url = f"{self.base_url}{path}"

        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method,
                url,
                json=json_body,
                params=params,
                headers=self._auth_headers,
            ) as resp,
        ):
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"API error ({resp.status}): {text}")
            if resp.status == 204:
                return None
            return await resp.json()

    # ------------------------------------------------------------------
    # Token exchange (for join)
    # ------------------------------------------------------------------

    async def exchange_gateway_token(self) -> dict[str, Any]:
        """Exchange API key for a gateway token with full response.

        Returns:
            Dict with ``token``, ``agent_config_id``, and ``name``.

        Raises:
            RuntimeError: If the exchange fails.
        """
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.base_url}/v1/token/gateway",
                headers={"X-API-Key": self.api_key},
            ) as resp,
        ):
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Gateway token exchange failed ({resp.status}): {text}")
            return await resp.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Meetings
    # ------------------------------------------------------------------

    async def list_meetings(self) -> dict[str, Any]:
        """List meetings the authenticated user has access to.

        Returns:
            Dict with ``items`` and ``total``.
        """
        return await self.request("GET", "/v1/meetings")

    async def create_meeting(
        self,
        title: str,
        *,
        platform: str = "kutana",
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a new meeting.

        Args:
            title: Human-readable title.
            platform: Meeting platform (default ``kutana``).
            scheduled_at: ISO 8601 datetime string. Defaults to now.

        Returns:
            Created meeting dict.
        """
        body: dict[str, Any] = {
            "title": title,
            "platform": platform,
            "scheduled_at": scheduled_at or datetime.now(tz=UTC).isoformat(),
        }
        return await self.request("POST", "/v1/meetings", json_body=body)

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Get a single meeting by ID.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Meeting dict.
        """
        return await self.request("GET", f"/v1/meetings/{meeting_id}")

    async def start_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Start a meeting (scheduled -> active).

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Updated meeting dict.
        """
        return await self.request("POST", f"/v1/meetings/{meeting_id}/start")

    async def end_meeting(self, meeting_id: str) -> dict[str, Any]:
        """End a meeting (active -> completed).

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Updated meeting dict.
        """
        return await self.request("POST", f"/v1/meetings/{meeting_id}/end")

    async def update_meeting(
        self,
        meeting_id: str,
        *,
        title: str | None = None,
        scheduled_at: str | None = None,
        platform: str | None = None,
    ) -> dict[str, Any]:
        """Update meeting fields.

        Args:
            meeting_id: Meeting UUID string.
            title: New title.
            scheduled_at: New scheduled time (ISO 8601).
            platform: New platform.

        Returns:
            Updated meeting dict.
        """
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if scheduled_at is not None:
            body["scheduled_at"] = scheduled_at
        if platform is not None:
            body["platform"] = platform
        return await self.request("PATCH", f"/v1/meetings/{meeting_id}", json_body=body)

    async def get_summary(self, meeting_id: str) -> dict[str, Any]:
        """Get or generate a meeting summary.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Summary dict.
        """
        return await self.request("GET", f"/v1/meetings/{meeting_id}/summary")

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def list_tasks(self, meeting_id: str | None = None) -> dict[str, Any]:
        """List tasks, optionally filtered by meeting.

        Args:
            meeting_id: Optional meeting UUID to filter by.

        Returns:
            Dict with ``items`` and ``total``.
        """
        params: dict[str, str] | None = None
        if meeting_id:
            params = {"meeting_id": meeting_id}
        return await self.request("GET", "/v1/tasks", params=params)

    async def create_task(
        self,
        meeting_id: str,
        description: str,
        *,
        priority: str = "medium",
        assignee_id: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task.

        Args:
            meeting_id: Meeting UUID string.
            description: Task description.
            priority: Priority (low, medium, high, critical).
            assignee_id: Optional assignee UUID.
            due_date: Optional due date (YYYY-MM-DD).

        Returns:
            Created task dict.
        """
        body: dict[str, Any] = {
            "meeting_id": meeting_id,
            "description": description,
            "priority": priority,
        }
        if assignee_id:
            body["assignee_id"] = assignee_id
        if due_date:
            body["due_date"] = due_date
        return await self.request("POST", "/v1/tasks", json_body=body)

    async def get_task(self, task_id: str) -> dict[str, Any]:
        """Get a single task by ID.

        Args:
            task_id: Task UUID string.

        Returns:
            Task dict.
        """
        return await self.request("GET", f"/v1/tasks/{task_id}")

    async def update_task_status(self, task_id: str, status: str) -> dict[str, Any]:
        """Update a task's status.

        Args:
            task_id: Task UUID string.
            status: New status (pending, in_progress, completed, cancelled).

        Returns:
            Updated task dict.
        """
        return await self.request(
            "PATCH",
            f"/v1/tasks/{task_id}",
            json_body={"status": status},
        )

    # ------------------------------------------------------------------
    # Turns
    # ------------------------------------------------------------------

    async def raise_hand(
        self,
        meeting_id: str,
        *,
        priority: str = "normal",
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Raise a hand to request a speaking turn.

        Args:
            meeting_id: Meeting UUID string.
            priority: "normal" (FIFO) or "urgent" (front of queue).
            topic: Optional topic to discuss.

        Returns:
            Dict with queue_position, hand_raise_id, was_promoted.
        """
        body: dict[str, Any] = {"priority": priority}
        if topic:
            body["topic"] = topic
        return await self.request(
            "POST",
            f"/v1/meetings/{meeting_id}/turns/raise",
            json_body=body,
        )

    async def get_turn_status(self, meeting_id: str) -> dict[str, Any]:
        """Get the current speaker queue for a meeting.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Dict with meeting_id, active_speaker_id, and queue entries.
        """
        return await self.request("GET", f"/v1/meetings/{meeting_id}/turns/status")

    async def finish_turn(self, meeting_id: str) -> dict[str, Any]:
        """Mark your speaking turn as finished.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Dict with status and optional next_speaker_id.
        """
        return await self.request("POST", f"/v1/meetings/{meeting_id}/turns/finish")

    async def cancel_hand(self, meeting_id: str) -> dict[str, Any]:
        """Cancel your raised hand.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Dict with cancelled boolean.
        """
        return await self.request("POST", f"/v1/meetings/{meeting_id}/turns/cancel")
