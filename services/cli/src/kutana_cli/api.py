"""REST API client for the Kutana AI API server."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from kutana_cli.config import get_api_url, get_token


class ApiError(Exception):
    """Raised when the API returns a non-success status."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


class KutanaClient:
    """Async HTTP client wrapping the Kutana REST API."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or get_api_url()).rstrip("/")
        self.token = token or get_token()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1{path}"
        async with aiohttp.ClientSession() as session, session.request(
            method,
            url,
            json=json_body,
            headers=self._headers(),
        ) as resp:
            if resp.status >= 400:
                body = await resp.json()
                detail = body.get("detail", str(body))
                raise ApiError(resp.status, detail)
            if resp.status == 204:
                return {}
            return await resp.json()  # type: ignore[no-any-return]

    # -- Auth ---------------------------------------------------------------

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate and return token + user info."""
        return await self._request(
            "POST", "/auth/login", json_body={"email": email, "password": password}
        )

    # -- Agents -------------------------------------------------------------

    async def list_agents(self) -> dict[str, Any]:
        """List all agents owned by the authenticated user."""
        return await self._request("GET", "/agents")

    async def create_agent(
        self, name: str, system_prompt: str = "You are a helpful meeting assistant."
    ) -> dict[str, Any]:
        """Create a new agent configuration."""
        return await self._request(
            "POST",
            "/agents",
            json_body={"name": name, "system_prompt": system_prompt},
        )

    # -- Meetings -----------------------------------------------------------

    async def list_meetings(self) -> dict[str, Any]:
        """List all meetings."""
        return await self._request("GET", "/meetings")

    async def create_meeting(self, title: str, scheduled_at: str) -> dict[str, Any]:
        """Create a new meeting."""
        return await self._request(
            "POST",
            "/meetings",
            json_body={"title": title, "scheduled_at": scheduled_at},
        )

    # -- API Keys -----------------------------------------------------------

    async def generate_key(
        self, agent_id: str, name: str = "default"
    ) -> dict[str, Any]:
        """Generate a new API key for an agent."""
        return await self._request(
            "POST",
            f"/agents/{agent_id}/keys",
            json_body={"name": name},
        )


def run_async(coro: Any) -> Any:
    """Run an async coroutine from sync context."""
    return asyncio.run(coro)
