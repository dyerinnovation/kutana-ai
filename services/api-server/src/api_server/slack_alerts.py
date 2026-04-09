"""Slack webhook integration for deploy notifications and critical alerts."""

from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)


async def send_slack_alert(
    webhook_url: str,
    text: str,
    *,
    level: str = "info",
) -> None:
    """Send a message to a Slack webhook.

    Args:
        webhook_url: The Slack incoming webhook URL.
        text: The message text to send.
        level: Alert level — "info", "warning", or "critical".
            Controls the color of the Slack attachment.
    """
    if not webhook_url:
        return

    color_map = {
        "info": "#16A34A",
        "warning": "#EAB308",
        "critical": "#EF4444",
    }

    payload = {
        "attachments": [
            {
                "color": color_map.get(level, "#16A34A"),
                "text": text,
                "footer": "Kutana AI Monitoring",
            }
        ]
    }

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(webhook_url, json=payload) as resp,
        ):
            if resp.status != 200:
                body = await resp.text()
                logger.warning("Slack webhook returned %d: %s", resp.status, body[:200])
    except Exception:
        logger.warning("Failed to send Slack alert", exc_info=True)
