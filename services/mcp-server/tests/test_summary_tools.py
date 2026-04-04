"""Tests for kutana_get_summary and kutana_set_context MCP tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_AGENT_ID = "agent-test-123"
MOCK_MEETING_ID = str(uuid4())


def _mock_identity(
    scopes: list[str] | None = None,
) -> MagicMock:
    """Create a mock MCPIdentity with given scopes."""
    identity = MagicMock()
    identity.agent_config_id = MOCK_AGENT_ID
    identity.scopes = scopes or [
        "meetings:read",
        "meetings:join",
        "meetings:chat",
        "turns:manage",
        "tasks:write",
    ]
    return identity


# ---------------------------------------------------------------------------
# kutana_get_summary tests
# ---------------------------------------------------------------------------


class TestKutanaGetSummary:
    """Tests for the kutana_get_summary MCP tool."""

    async def test_get_summary_success(self) -> None:
        """get_summary returns structured summary JSON."""
        from mcp_server import main as mcp_main

        mock_summary = {
            "meeting_id": MOCK_MEETING_ID,
            "title": "Sprint Planning",
            "duration_minutes": 45,
            "participant_count": 3,
            "key_points": ["Discussed Q2 roadmap", "Reviewed velocity"],
            "decisions": ["Prioritize auth feature"],
            "task_count": 5,
            "ended_at": "2026-03-26T10:00:00Z",
            "generated_at": "2026-03-26T10:01:00Z",
        }

        mock_client = MagicMock()
        mock_client.get_summary = AsyncMock(return_value=mock_summary)

        identity = _mock_identity()

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=None),
            patch.object(mcp_main, "_get_api_client", return_value=mock_client),
            patch.object(mcp_main, "log_tool_call"),
        ):
            result = await mcp_main.kutana_get_summary(MOCK_MEETING_ID)

        data = json.loads(result)
        assert data["meeting_id"] == MOCK_MEETING_ID
        assert data["title"] == "Sprint Planning"
        assert len(data["key_points"]) == 2
        assert data["task_count"] == 5

    async def test_get_summary_invalid_meeting_id(self) -> None:
        """get_summary returns error for invalid meeting ID."""
        from mcp_server import main as mcp_main

        result = await mcp_main.kutana_get_summary("not-a-uuid")
        data = json.loads(result)
        assert "error" in data

    async def test_get_summary_scope_denied(self) -> None:
        """get_summary returns scope error when meetings:read is missing."""
        from mcp_server import main as mcp_main

        identity = _mock_identity(scopes=["tasks:write"])
        scope_error = json.dumps({"error": "insufficient_scope"})

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=scope_error),
        ):
            result = await mcp_main.kutana_get_summary(MOCK_MEETING_ID)

        data = json.loads(result)
        assert data["error"] == "insufficient_scope"

    async def test_get_summary_api_error(self) -> None:
        """get_summary returns error when API call fails."""
        from mcp_server import main as mcp_main

        mock_client = MagicMock()
        mock_client.get_summary = AsyncMock(
            side_effect=RuntimeError("Get summary failed (500): Internal Server Error")
        )

        identity = _mock_identity()

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=None),
            patch.object(mcp_main, "_get_api_client", return_value=mock_client),
        ):
            result = await mcp_main.kutana_get_summary(MOCK_MEETING_ID)

        data = json.loads(result)
        assert "error" in data
        assert "500" in data["error"]


# ---------------------------------------------------------------------------
# kutana_set_context tests
# ---------------------------------------------------------------------------


class TestKutanaSetContext:
    """Tests for the kutana_set_context MCP tool."""

    async def test_set_context_success(self) -> None:
        """set_context publishes context to the meeting data channel."""
        from mcp_server import main as mcp_main

        identity = _mock_identity()

        mock_gw = MagicMock()
        mock_gw.meeting_id = MOCK_MEETING_ID
        mock_gw.publish_to_channel = AsyncMock()

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=None),
            patch.object(mcp_main, "_gateway_client", mock_gw),
            patch.object(mcp_main, "log_tool_call"),
        ):
            result = await mcp_main.kutana_set_context(
                MOCK_MEETING_ID,
                "Previous sprint: completed 15 story points.",
            )

        data = json.loads(result)
        assert data["status"] == "context_injected"
        assert data["meeting_id"] == MOCK_MEETING_ID
        assert data["context_length"] > 0
        mock_gw.publish_to_channel.assert_awaited_once()

    async def test_set_context_not_in_meeting(self) -> None:
        """set_context returns error when not connected to a meeting."""
        from mcp_server import main as mcp_main

        identity = _mock_identity()

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=None),
            patch.object(mcp_main, "_gateway_client", None),
        ):
            result = await mcp_main.kutana_set_context(
                MOCK_MEETING_ID,
                "Some context",
            )

        data = json.loads(result)
        assert "error" in data
        assert "Not in a meeting" in data["error"]

    async def test_set_context_truncates_long_input(self) -> None:
        """set_context truncates context exceeding 5000 chars."""
        from mcp_server import main as mcp_main

        identity = _mock_identity()

        mock_gw = MagicMock()
        mock_gw.meeting_id = MOCK_MEETING_ID
        mock_gw.publish_to_channel = AsyncMock()

        long_context = "x" * 6000

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=None),
            patch.object(mcp_main, "_gateway_client", mock_gw),
            patch.object(mcp_main, "log_tool_call"),
        ):
            result = await mcp_main.kutana_set_context(
                MOCK_MEETING_ID,
                long_context,
            )

        data = json.loads(result)
        assert data["status"] == "context_injected"
        # The context_length should be <= 5000 (after truncation + sanitization)
        assert data["context_length"] <= 5000

    async def test_set_context_scope_denied(self) -> None:
        """set_context requires meetings:chat scope."""
        from mcp_server import main as mcp_main

        identity = _mock_identity(scopes=["meetings:read"])
        scope_error = json.dumps({"error": "insufficient_scope"})

        with (
            patch.object(mcp_main, "_ensure_authenticated", return_value=identity),
            patch.object(mcp_main, "_security_check", return_value=scope_error),
        ):
            result = await mcp_main.kutana_set_context(
                MOCK_MEETING_ID,
                "Some context",
            )

        data = json.loads(result)
        assert data["error"] == "insufficient_scope"

    async def test_set_context_invalid_meeting_id(self) -> None:
        """set_context returns error for invalid meeting ID."""
        from mcp_server import main as mcp_main

        result = await mcp_main.kutana_set_context("bad-id", "Some context")
        data = json.loads(result)
        assert "error" in data


# ---------------------------------------------------------------------------
# Scope registration tests
# ---------------------------------------------------------------------------


class TestScopeRegistration:
    """Verify new tools are registered in the scope map."""

    def test_get_summary_scope_registered(self) -> None:
        """get_summary is mapped to meetings:read."""
        from mcp_server.security.scopes import TOOL_REQUIRED_SCOPE

        assert "get_summary" in TOOL_REQUIRED_SCOPE
        assert TOOL_REQUIRED_SCOPE["get_summary"] == "meetings:read"

    def test_set_context_scope_registered(self) -> None:
        """set_context is mapped to meetings:chat."""
        from mcp_server.security.scopes import TOOL_REQUIRED_SCOPE

        assert "set_context" in TOOL_REQUIRED_SCOPE
        assert TOOL_REQUIRED_SCOPE["set_context"] == "meetings:chat"


# ---------------------------------------------------------------------------
# Rate limit registration tests
# ---------------------------------------------------------------------------


class TestRateLimitRegistration:
    """Verify new tools have rate limit entries."""

    def test_get_summary_rate_limit(self) -> None:
        """get_summary has a rate limit of 10 per minute."""
        from mcp_server.security.rate_limit import TOOL_RATE_LIMITS

        assert "get_summary" in TOOL_RATE_LIMITS
        assert TOOL_RATE_LIMITS["get_summary"] == (10, 60)

    def test_set_context_rate_limit(self) -> None:
        """set_context has a rate limit of 10 per minute."""
        from mcp_server.security.rate_limit import TOOL_RATE_LIMITS

        assert "set_context" in TOOL_RATE_LIMITS
        assert TOOL_RATE_LIMITS["set_context"] == (10, 60)
