"""Slack webhook integration for sending notifications."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from uuid import UUID

    from kutana_core.models.task import Task

logger = logging.getLogger(__name__)


class SlackBot:
    """Sends notifications to Slack via incoming webhooks.

    Supports sending task notifications and meeting summaries
    to a configured Slack channel.

    Attributes:
        _webhook_url: The Slack incoming webhook URL.
    """

    def __init__(self, webhook_url: str) -> None:
        """Initialise the Slack bot.

        Args:
            webhook_url: Slack incoming webhook URL.
        """
        self._webhook_url = webhook_url

    async def send_task_notification(self, task: Task) -> None:
        """Send a new-task notification to Slack.

        Formats the task details into a Slack message payload and
        posts it to the configured webhook URL.

        Args:
            task: The task to notify about.
        """
        assignee_text = f"Assigned to: `{task.assignee_id}`" if task.assignee_id else "Unassigned"

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "New Task Extracted",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": (f"*Description:*\n{task.description}"),
                        },
                        {
                            "type": "mrkdwn",
                            "text": (
                                f"*Priority:* {task.priority.value}\n"
                                f"*Status:* {task.status.value}\n"
                                f"{assignee_text}"
                            ),
                        },
                    ],
                },
            ],
        }

        await self._post(payload)
        logger.info("Slack task notification sent: task_id=%s", task.id)

    async def send_meeting_summary(
        self,
        meeting_id: UUID,
        summary: str,
    ) -> None:
        """Send a meeting summary to Slack.

        Args:
            meeting_id: The ID of the meeting being summarised.
            summary: The human-readable meeting summary text.
        """
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Meeting Summary",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (f"*Meeting:* `{meeting_id}`\n\n{summary}"),
                    },
                },
            ],
        }

        await self._post(payload)
        logger.info(
            "Slack meeting summary sent: meeting_id=%s",
            meeting_id,
        )

    async def _post(self, payload: dict[str, object]) -> None:
        """POST a JSON payload to the Slack webhook.

        Args:
            payload: The Slack Block Kit message payload.

        Raises:
            httpx.HTTPStatusError: If Slack returns a non-2xx response.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._webhook_url,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
