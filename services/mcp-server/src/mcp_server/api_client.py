"""HTTP client for the Kutana API server."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class ApiClient:
    """Async HTTP client for the Kutana API server.

    Handles token exchange and CRUD operations against the API.
    Supports both API key auth and Bearer JWT auth (for MCP tokens).

    Attributes:
        base_url: API server base URL.
        api_key: Raw API key for authentication.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        bearer_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._bearer_token = bearer_token
        self._gateway_token: str | None = None

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Return auth headers, preferring Bearer token over API key."""
        if self._bearer_token:
            return {"Authorization": f"Bearer {self._bearer_token}"}
        return {"X-API-Key": self.api_key}

    def set_bearer_token(self, token: str) -> None:
        """Set a Bearer JWT for authenticated downstream API calls.

        Args:
            token: The JWT to use for Authorization headers.
        """
        self._bearer_token = token

    async def exchange_for_gateway_token(self) -> str:
        """Exchange the API key for a short-lived gateway JWT.

        Returns:
            The gateway JWT string.

        Raises:
            RuntimeError: If the token exchange fails.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/token/gateway",
                headers={"X-API-Key": self.api_key},
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Token exchange failed ({resp.status}): {text}")
                data = await resp.json()
                self._gateway_token = data["token"]
                return self._gateway_token

    async def exchange_for_mcp_token(self) -> str:
        """Exchange the API key for a short-lived MCP JWT.

        Returns:
            The MCP JWT string.

        Raises:
            RuntimeError: If the token exchange fails.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/token/mcp",
                headers={"X-API-Key": self.api_key},
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"MCP token exchange failed ({resp.status}): {text}"
                    )
                data = await resp.json()
                token = data["token"]
                self._bearer_token = token
                return token

    @property
    def gateway_token(self) -> str | None:
        """The cached gateway JWT, if available."""
        return self._gateway_token

    async def list_meetings(self) -> list[dict[str, Any]]:
        """List available meetings.

        Returns:
            List of meeting dicts.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/v1/meetings",
                headers=self._auth_headers,
            ) as resp:
                data = await resp.json()
                return data.get("items", [])

    async def get_tasks(self, meeting_id: str) -> list[dict[str, Any]]:
        """Get tasks for a meeting.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            List of task dicts.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/v1/tasks",
                params={"meeting_id": meeting_id},
                headers=self._auth_headers,
            ) as resp:
                data = await resp.json()
                return data.get("items", [])

    async def create_task(
        self,
        meeting_id: str,
        description: str,
        priority: str = "medium",
    ) -> dict[str, Any]:
        """Create a task.

        Args:
            meeting_id: Meeting UUID string.
            description: Task description.
            priority: Task priority (low, medium, high, critical).

        Returns:
            The created task dict.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/tasks",
                json={
                    "meeting_id": meeting_id,
                    "description": description,
                    "priority": priority,
                },
                headers=self._auth_headers,
            ) as resp:
                return await resp.json()

    async def create_meeting(
        self,
        title: str | None = None,
        platform: str = "kutana",
        scheduled_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a new meeting.

        Args:
            title: Optional meeting title.
            platform: Meeting platform (default: "kutana").
            scheduled_at: ISO 8601 datetime string. Defaults to now.

        Returns:
            The created meeting dict.
        """
        from datetime import UTC, datetime

        body: dict[str, Any] = {
            "platform": platform,
            "scheduled_at": scheduled_at or datetime.now(tz=UTC).isoformat(),
        }
        if title is not None:
            body["title"] = title

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/meetings",
                json=body,
                headers=self._auth_headers,
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise RuntimeError(
                        f"Create meeting failed ({resp.status}): {text}"
                    )
                return await resp.json()

    async def start_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Start a meeting (transition scheduled → active).

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            The updated meeting dict.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/meetings/{meeting_id}/start",
                headers=self._auth_headers,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Start meeting failed ({resp.status}): {text}"
                    )
                return await resp.json()

    async def get_summary(self, meeting_id: str) -> dict[str, Any]:
        """Get or generate a meeting summary.

        Calls the API server summary endpoint which returns a cached
        summary or generates one on-demand via Haiku.

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            Summary dict with key_points, decisions, task_count, etc.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/v1/meetings/{meeting_id}/summary",
                headers=self._auth_headers,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Get summary failed ({resp.status}): {text}"
                    )
                return await resp.json()

    async def end_meeting(self, meeting_id: str) -> dict[str, Any]:
        """End a meeting (transition active → completed).

        Args:
            meeting_id: Meeting UUID string.

        Returns:
            The updated meeting dict.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/meetings/{meeting_id}/end",
                headers=self._auth_headers,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"End meeting failed ({resp.status}): {text}"
                    )
                return await resp.json()
