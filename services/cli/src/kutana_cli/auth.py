"""Authentication commands for the Kutana CLI."""

from __future__ import annotations

import asyncio
from typing import Any

import click

from kutana_cli.client import KutanaClient
from kutana_cli.config import get_api_url, load_config, save_config
from kutana_cli.output import output, print_error


@click.group()
def auth() -> None:
    """Manage API authentication."""


@auth.command()
@click.option("--url", required=True, help="Kutana server URL (e.g. https://dev.kutana.ai).")
@click.option("--api-key", required=True, help="Agent API key (starts with kutana_).")
@click.pass_context
def login(ctx: click.Context, url: str, api_key: str) -> None:
    """Save credentials and verify connectivity.

    Tests the API key by exchanging it for a JWT token. On success,
    saves the URL and key to ~/.kutana/config.json.
    """
    use_json: bool = ctx.obj["use_json"]

    config = load_config()
    config["url"] = url.rstrip("/")
    config["api_key"] = api_key

    api_url = get_api_url(config)

    try:
        client = KutanaClient(api_url, api_key)
        result: dict[str, Any] = asyncio.run(client.authenticate())
    except Exception as exc:
        print_error(f"Login failed: {exc}")
        return  # unreachable -- print_error exits

    save_config(config)
    output(
        {
            "status": "authenticated",
            "url": config["url"],
            "api_key": _mask_key(api_key),
            "agent_config_id": result.get("agent_config_id"),
            "name": result.get("name"),
        },
        use_json=use_json,
    )


@auth.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current authentication configuration and test the connection."""
    use_json: bool = ctx.obj["use_json"]
    config: dict[str, Any] = ctx.obj["config"]

    if not config.get("api_key"):
        output(
            {"status": "not_configured", "hint": "Run: kutana auth login --url URL --api-key KEY"},
            use_json=use_json,
        )
        return

    api_url = get_api_url(config)
    client = KutanaClient(api_url, config["api_key"])

    try:
        result: dict[str, Any] = asyncio.run(client.authenticate())
        data: dict[str, Any] = {
            "status": "connected",
            "url": config.get("url", "not set"),
            "api_key": _mask_key(config["api_key"]),
            "agent_config_id": result.get("agent_config_id"),
            "name": result.get("name"),
        }
    except Exception as exc:
        data = {
            "status": "error",
            "url": config.get("url", "not set"),
            "api_key": _mask_key(config["api_key"]),
            "error": str(exc),
        }

    output(data, use_json=use_json)


def _mask_key(key: str) -> str:
    """Mask an API key for display, showing only the first 8 and last 4 chars.

    Args:
        key: The raw API key.

    Returns:
        Masked string like ``kutana_a...xyzw``.
    """
    if len(key) <= 12:
        return key[:4] + "..." + key[-2:]
    return key[:8] + "..." + key[-4:]
