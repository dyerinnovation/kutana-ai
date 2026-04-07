"""Configuration and session management for the Kutana CLI.

Config and session files live in ``~/.kutana/``:
- ``config.json`` -- persisted URL and API key.
- ``session.json`` -- ephemeral gateway token, meeting ID, agent config ID.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    """Derive the API base URL from config.

    The API is served at ``{base_url}/api`` in production, and routes
    are prefixed with ``/v1``.

    Args:
        config: Configuration dict with optional ``url`` key.

    Returns:
        API base URL string (e.g. ``https://dev.kutana.ai/api``).
    """
    base = config.get("url", DEFAULT_URL).rstrip("/")
    return f"{base}/api"


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
