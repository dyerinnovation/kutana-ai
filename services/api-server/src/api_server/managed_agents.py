"""Anthropic Managed Agents integration.

Forward-looking module: wraps the Anthropic beta managed-agents API to
create, manage, and interact with hosted agent sessions backed by
Anthropic's infrastructure.

**SDK availability:** As of anthropic SDK v0.84.0, the managed agents API
(``client.beta.agents``, ``client.beta.sessions``, ``client.beta.environments``,
``client.beta.vaults``) does not exist. All public functions in this module
are guarded with a runtime check and will log a warning + return a
sentinel value until a future SDK version ships the API.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import anthropic

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Runtime availability check
# ---------------------------------------------------------------------------

_MANAGED_AGENTS_AVAILABLE: bool = False

try:
    _probe_client = anthropic.AsyncAnthropic(api_key="probe")
    # Check if the beta namespace exposes the agents resource
    if hasattr(_probe_client.beta, "agents") and hasattr(_probe_client.beta, "sessions"):
        _MANAGED_AGENTS_AVAILABLE = True
    del _probe_client
except Exception:
    pass

if not _MANAGED_AGENTS_AVAILABLE:
    logger.warning(
        "Anthropic managed agents API is not available in the current SDK version. "
        "All managed agent operations will be no-ops until a compatible SDK is installed."
    )


def _require_api(func_name: str) -> bool:
    """Check if the managed agents API is available.

    Args:
        func_name: Name of the calling function (for log messages).

    Returns:
        True if available, False otherwise.
    """
    if not _MANAGED_AGENTS_AVAILABLE:
        logger.warning(
            "%s called but managed agents API is not available — returning sentinel.",
            func_name,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MCP_SERVER_URL = "https://api-dev.kutana.ai/mcp/"
DEFAULT_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: anthropic.AsyncAnthropic | None = None


def _get_client(api_key: str) -> anthropic.AsyncAnthropic:
    """Return a cached async Anthropic client.

    Args:
        api_key: Anthropic API key.

    Returns:
        Async Anthropic client instance.
    """
    global _client
    if _client is None or _client.api_key != api_key:
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Agent registration
# ---------------------------------------------------------------------------


async def register_agents(
    api_key: str,
    templates: list[dict[str, Any]],
) -> dict[str, str]:
    """Create or update Anthropic managed agent definitions (idempotent).

    For each template, creates an Anthropic agent with the template's system
    prompt, connected to the Kutana MCP server.

    Args:
        api_key: Anthropic API key.
        templates: List of dicts with keys: id, name, system_prompt.

    Returns:
        Mapping of template_id -> anthropic_agent_id.
    """
    if not _require_api("register_agents"):
        return {}

    client = _get_client(api_key)
    result: dict[str, str] = {}

    for tmpl in templates:
        agent = await client.beta.agents.create(
            name=tmpl["name"],
            model=DEFAULT_MODEL,
            system=tmpl["system_prompt"],
            mcp_servers=[
                {
                    "type": "url",
                    "name": "kutana",
                    "url": MCP_SERVER_URL,
                }
            ],
            tools=[
                {
                    "type": "mcp_toolset",
                    "mcp_server_name": "kutana",
                }
            ],
        )
        result[tmpl["id"]] = agent.id
        logger.info("Registered Anthropic agent %s for template %s", agent.id, tmpl["name"])

    return result


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


async def get_or_create_environment(api_key: str) -> str:
    """Get or create a shared cloud environment for Kutana sessions.

    Args:
        api_key: Anthropic API key.

    Returns:
        Environment ID string.
    """
    if not _require_api("get_or_create_environment"):
        return ""

    client = _get_client(api_key)
    env = await client.beta.environments.create(
        name="kutana-cloud",
    )
    return env.id


# ---------------------------------------------------------------------------
# Vault (MCP auth credentials)
# ---------------------------------------------------------------------------


async def create_vault(api_key: str, jwt: str) -> str:
    """Register MCP authentication credentials in an Anthropic vault.

    Args:
        api_key: Anthropic API key.
        jwt: JWT token for MCP server authentication.

    Returns:
        Vault ID string.
    """
    if not _require_api("create_vault"):
        return ""

    client = _get_client(api_key)
    vault = await client.beta.vaults.create(
        name="kutana-mcp-auth",
        secrets=[
            {
                "name": "authorization",
                "value": f"Bearer {jwt}",
            }
        ],
    )
    return vault.id


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


async def start_session(
    api_key: str,
    agent_id: str,
    env_id: str,
    vault_id: str,
) -> str:
    """Create a new Anthropic managed agent session.

    Args:
        api_key: Anthropic API key.
        agent_id: Anthropic agent ID.
        env_id: Environment ID.
        vault_id: Vault ID with MCP credentials.

    Returns:
        Session ID string.
    """
    if not _require_api("start_session"):
        return ""

    from api_server.langfuse_client import create_trace

    trace = create_trace(
        name="managed-agent-start-session",
        metadata={"agent_id": agent_id, "env_id": env_id},
        tags=["managed-agent", "session-start"],
    )

    client = _get_client(api_key)
    session = await client.beta.sessions.create(
        agent=agent_id,
        environment_id=env_id,
        vault_ids=[vault_id],
    )

    if trace is not None:
        trace.update(output={"session_id": session.id})

    logger.info("Started Anthropic session %s for agent %s", session.id, agent_id)
    return session.id


async def send_message(api_key: str, session_id: str, text: str) -> None:
    """Send a user message to an active Anthropic session.

    Args:
        api_key: Anthropic API key.
        session_id: Active session ID.
        text: Message text to send.
    """
    if not _require_api("send_message"):
        return

    from api_server.langfuse_client import get_langfuse

    langfuse = get_langfuse()
    generation = None
    if langfuse is not None:
        generation = langfuse.generation(
            name="managed-agent-send-message",
            metadata={"session_id": session_id},
            input=text[:500],  # Truncate for Langfuse display
        )

    client = _get_client(api_key)
    await client.beta.sessions.events.send(
        session_id,
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": text}],
            }
        ],
    )

    if generation is not None:
        generation.end(output="message_sent")


async def stream_events(api_key: str, session_id: str) -> AsyncIterator[Any]:
    """Stream SSE events from an Anthropic session.

    Yields agent.message, agent.mcp_tool_use, session.status_idle, etc.

    Args:
        api_key: Anthropic API key.
        session_id: Active session ID.

    Yields:
        SSE event objects from the Anthropic API.
    """
    if not _require_api("stream_events"):
        return

    from api_server.langfuse_client import get_langfuse

    langfuse = get_langfuse()
    span = None
    if langfuse is not None:
        span = langfuse.span(
            name="managed-agent-stream-events",
            metadata={"session_id": session_id},
        )

    event_count = 0
    client = _get_client(api_key)
    async with client.beta.sessions.events.stream(session_id) as stream:
        async for event in stream:
            event_count += 1
            yield event

    if span is not None:
        span.end(output={"events_streamed": event_count})


async def end_session(api_key: str, session_id: str) -> None:
    """End an Anthropic session by sending a user.interrupt event.

    Args:
        api_key: Anthropic API key.
        session_id: Session ID to end.
    """
    if not _require_api("end_session"):
        return

    from api_server.langfuse_client import create_trace

    trace = create_trace(
        name="managed-agent-end-session",
        metadata={"session_id": session_id},
        tags=["managed-agent", "session-end"],
    )

    client = _get_client(api_key)
    try:
        await client.beta.sessions.events.send(
            session_id,
            events=[{"type": "user.interrupt"}],
        )
        if trace is not None:
            trace.update(output={"status": "ended"})
        logger.info("Ended Anthropic session %s", session_id)
    except anthropic.APIError:
        if trace is not None:
            trace.update(output={"status": "already_closed"})
        logger.warning("Failed to end Anthropic session %s (may already be closed)", session_id)
