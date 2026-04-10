"""Agent registry: maps template slugs to pre-created Anthropic agent IDs.

Pre-created agents live in the Anthropic console. This registry maps
each Kutana template to the correct Anthropic agent ID for the active
tier (default/haiku/opus), controlled by a single env var.

Usage::

    from api_server.agent_registry import get_agent_id

    agent_id = get_agent_id("meeting-notetaker")  # uses KUTANA_AGENT_TIER
    agent_id = get_agent_id("meeting-notetaker", tier="haiku")  # explicit
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

#: Which tier of pre-created agents to use.
#: Set via ``KUTANA_AGENT_TIER`` env var: "default" | "haiku" | "opus"
AGENT_TIER: str = os.environ.get("KUTANA_AGENT_TIER", "default")

# ---------------------------------------------------------------------------
# Registry: template slug → { tier: anthropic_agent_id }
# ---------------------------------------------------------------------------
# These IDs come from the Anthropic console. Update them when agents are
# re-created (e.g. via ``scripts/sync_agents.py``).

AGENT_REGISTRY: dict[str, dict[str, str]] = {
    "meeting-notetaker": {
        "default": "agent_011CZtcwu1SmExYSKgwJz4b9",
        "haiku": "agent_011CZtdpTFK4Wd3CKfoQENtt",
    },
    "meeting-summarizer": {
        "default": "agent_011CZtcwv8fTmDZGDLiKsQJQ",
        "haiku": "agent_011CZtdpUKJx4WicPxBRegPt",
    },
    "action-item-tracker": {
        "default": "agent_011CZtcwwYFMqbiF3SAJMcqK",
        "haiku": "agent_011CZtdpVMp87MsxaDcqQDjc",
    },
    "decision-logger": {
        "default": "agent_011CZtcwxZWauqhhWrHAW83Y",
    },
    "standup-facilitator": {
        "default": "agent_011CZtcwyQ81he3LZtJgGPWf",
    },
    "code-discussion-tracker": {
        "default": "agent_011CZtcwzV7A5QnfjdnSDwPN",
    },
    "sprint-retro-coach": {
        "default": "agent_011CZtcx38bdLcBVPF1KTJ6g",
    },
    "sprint-planner": {
        "default": "agent_011CZtcx4ibfuvRE7AeZ4uuR",
        "opus": "agent_011CZtdpWr7kTSDfSUQP7gmz",
    },
    "user-interviewer": {
        "default": "agent_011CZtcx5vmuQzMwgAHZfame",
        "opus": "agent_011CZtdpYN9SpSAZHHDPkbbe",
    },
    "initial-interviewer": {
        "default": "agent_011CZtcx73zdHMNHuGQnhdEJ",
        "opus": "agent_011CZtdpZbJoRGLdvpjDiKof",
    },
}

#: Mapping from AgentTemplateORM.name → registry slug.
#: The DB stores display names; the registry uses slugs.
TEMPLATE_NAME_TO_SLUG: dict[str, str] = {
    "Meeting Notetaker": "meeting-notetaker",
    "Meeting Summarizer": "meeting-summarizer",
    "Action Item Tracker": "action-item-tracker",
    "Decision Logger": "decision-logger",
    "Standup Facilitator": "standup-facilitator",
    "Code Discussion Tracker": "code-discussion-tracker",
    "Sprint Retro Coach": "sprint-retro-coach",
    "Sprint Planner": "sprint-planner",
    "User Interviewer": "user-interviewer",
    "Initial Interviewer": "initial-interviewer",
}


class AgentNotFoundError(Exception):
    """Raised when no pre-created agent matches the requested template/tier."""


def get_agent_id(
    template_slug: str,
    *,
    tier: str | None = None,
) -> str:
    """Look up the pre-created Anthropic agent ID for a template.

    Args:
        template_slug: Registry slug (e.g. "meeting-notetaker").
        tier: Override the global ``KUTANA_AGENT_TIER``. Defaults to
            the ``KUTANA_AGENT_TIER`` env var (typically "default").

    Returns:
        Anthropic agent ID string.

    Raises:
        AgentNotFoundError: If the slug or tier has no registered agent.
    """
    effective_tier = tier or AGENT_TIER

    tiers = AGENT_REGISTRY.get(template_slug)
    if tiers is None:
        raise AgentNotFoundError(f"No agent registered for template '{template_slug}'")

    agent_id = tiers.get(effective_tier)
    if agent_id is None:
        # Fall back to "default" tier if the requested tier doesn't exist
        agent_id = tiers.get("default")
        if agent_id is None:
            raise AgentNotFoundError(
                f"No agent registered for template '{template_slug}' "
                f"at tier '{effective_tier}' (no default fallback either)"
            )
        logger.info(
            "Tier '%s' not available for '%s', falling back to default",
            effective_tier,
            template_slug,
        )

    return agent_id


def get_agent_id_by_name(
    template_name: str,
    *,
    tier: str | None = None,
) -> str:
    """Look up agent ID using the template display name.

    Convenience wrapper that translates DB display names
    (e.g. "Meeting Notetaker") to registry slugs.

    Args:
        template_name: Display name from AgentTemplateORM.name.
        tier: Optional tier override.

    Returns:
        Anthropic agent ID string.

    Raises:
        AgentNotFoundError: If the name is unknown or no agent exists.
    """
    slug = TEMPLATE_NAME_TO_SLUG.get(template_name)
    if slug is None:
        raise AgentNotFoundError(f"Unknown template name '{template_name}'")
    return get_agent_id(slug, tier=tier)
