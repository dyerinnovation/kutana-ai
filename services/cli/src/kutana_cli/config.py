"""Configuration management for Kutana CLI.

Stores credentials and settings in ~/.kutana/config.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".kutana"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "api_url": "http://localhost:8000",
    "token": None,
}


def _ensure_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config from disk, returning defaults if no file exists."""
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    return json.loads(CONFIG_FILE.read_text())  # type: ignore[no-any-return]


def save_config(config: dict[str, Any]) -> None:
    """Persist config to disk."""
    _ensure_dir()
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def get_token() -> str | None:
    """Return the stored JWT token, or None."""
    return load_config().get("token")  # type: ignore[no-any-return]


def get_api_url() -> str:
    """Return the API base URL."""
    return load_config().get("api_url", DEFAULT_CONFIG["api_url"])  # type: ignore[no-any-return]
