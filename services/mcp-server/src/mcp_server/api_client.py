"""HTTP client for the Convene API server."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class ApiClient:
    """Async HTTP client for the Convene API server.

    Handles token exchange and CRUD operations against the API.

    Attributes:
        base_url: API server base URL.
        api_key: Raw API key for authentication.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._gateway_token: str | None = None

    async def exchange_for_gateway_token(self) -> str:
        """Exchange the API key for a short-lived gateway JWT.

        Returns:
            The gateway JWT string.

        Raises:
            RuntimeError: If the token exchange fails.
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/token/gateway",
                headers={"X-API-Key": self.api_key},
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Token exchange failed ({resp.status}): {text}")
                data = await resp.json()
                self._gateway_token = data["token"]
                return self._gateway_token

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
                f"{self.base_url}/api/v1/meetings",
                headers={"X-API-Key": self.api_key},
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
                f"{self.base_url}/api/v1/tasks",
                params={"meeting_id": meeting_id},
                headers={"X-API-Key": self.api_key},
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
                f"{self.base_url}/api/v1/tasks",
                json={
                    "meeting_id": meeting_id,
                    "description": description,
                    "priority": priority,
                },
                headers={"X-API-Key": self.api_key},
            ) as resp:
                return await resp.json()
