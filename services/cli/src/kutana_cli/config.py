"""Configuration and session management for the Kutana CLI.

Config and session files live in ``~/.kutana/``:
- ``config.json`` -- persisted URL and API key.
- ``session.json`` -- ephemeral gateway token, meeting ID, agent config ID.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".kutana"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_FILE = CONFIG_DIR / "session.json"

DEFAULT_URL = "https://dev.kutana.ai"


def _ensure_dir() -> None:
    """Create the config directory if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Config (persistent)
# ---------------------------------------------------------------------------


def load_config() -> dict[str, Any]:
    """Load the saved configuration.

    Returns:
        Dict with ``url`` and ``api_key`` keys (may be empty).
    """
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text())  # type: ignore[no-any-return]


def save_config(config: dict[str, Any]) -> None:
    """Persist the configuration to disk.

    Args:
        config: Configuration dict to save.
    """
    _ensure_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")
    # Restrict permissions to owner only
    CONFIG_FILE.chmod(0o600)


def get_api_url(config: dict[str, Any]) -> str:
    """Return the API base URL from config.

    Prefers the discovered ``api_url`` if present, otherwise falls back
    to the base ``url`` (routes are at ``/v1/...`` directly).

    Args:
        config: Configuration dict with optional ``api_url`` or ``url`` key.

    Returns:
        API base URL string (e.g. ``https://api.kutana.ai``).
    """
    if config.get("api_url"):
        return config["api_url"].rstrip("/")
    return config.get("url", DEFAULT_URL).rstrip("/")


async def discover_endpoints(base_url: str) -> dict[str, str]:
    """Fetch endpoint URLs from the well-known discovery document.

    Tries ``{base_url}/.well-known/kutana.json``. On failure, falls back
    to convention: ``api.{domain}`` and ``ws.{domain}``.

    Args:
        base_url: The user-provided server URL (e.g. ``https://kutana.ai``).

    Returns:
        Dict with ``api_url`` and ``ws_url`` keys.
    """
    base_url = base_url.rstrip("/")
    discovery_url = f"{base_url}/.well-known/kutana.json"

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(discovery_url, timeout=aiohttp.ClientTimeout(total=5)) as resp,
        ):
            if resp.status == 200:
                data = await resp.json()
                api_url = data.get("api_url", "").rstrip("/")
                ws_url = data.get("ws_url", "").rstrip("/")
                if api_url and ws_url:
                    logger.info("Discovered endpoints: api=%s ws=%s", api_url, ws_url)
                    return {"api_url": api_url, "ws_url": ws_url}
            logger.warning("Discovery returned %s, falling back to convention", resp.status)
    except Exception as exc:
        logger.warning("Discovery fetch failed (%s), falling back to convention", exc)

    # Convention fallback: prepend api. / ws. to the domain
    parsed = urlparse(base_url)
    domain = parsed.hostname or parsed.netloc
    scheme = parsed.scheme or "https"
    api_url = f"{scheme}://api.{domain}"
    ws_scheme = "wss" if scheme == "https" else "ws"
    ws_url = f"{ws_scheme}://ws.{domain}"
    logger.info("Using convention endpoints: api=%s ws=%s", api_url, ws_url)
    return {"api_url": api_url, "ws_url": ws_url}


# ---------------------------------------------------------------------------
# Session (ephemeral)
# ---------------------------------------------------------------------------


def load_session() -> dict[str, Any]:
    """Load the current session state.

    Returns:
        Dict with ``gateway_token``, ``meeting_id``, ``agent_config_id``
        (may be empty if no active session).
    """
    if not SESSION_FILE.exists():
        return {}
    return json.loads(SESSION_FILE.read_text())  # type: ignore[no-any-return]


def save_session(session: dict[str, Any]) -> None:
    """Persist session state to disk.

    Args:
        session: Session dict with meeting_id, gateway_token, etc.
    """
    _ensure_dir()
    SESSION_FILE.write_text(json.dumps(session, indent=2) + "\n")
    SESSION_FILE.chmod(0o600)


def clear_session() -> None:
    """Remove the session file."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
