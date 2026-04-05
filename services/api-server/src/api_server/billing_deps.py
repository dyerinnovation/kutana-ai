"""Tier-based limit enforcement for billing plans.

Defines per-tier feature limits and FastAPI helpers that raise 403
when a user has hit a limit or is trying to use a feature above their
tier. Endpoints should call `require_tier(...)` or the specific
`check_*` helpers inside their handlers after resolving the user.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — runtime use in helpers

from kutana_core.database.models import (
    AgentConfigORM,
    FeedORM,
    UserORM,
)

# ---------------------------------------------------------------------------
# Tier limits table
# ---------------------------------------------------------------------------

# `None` means unlimited. Trial users share the "basic" tier.
TIER_ORDER: dict[str, int] = {
    "basic": 0,
    "pro": 1,
    "business": 2,
    "enterprise": 3,
}

MEETINGS_PER_MONTH: dict[str, int | None] = {
    "basic": 10,
    "pro": None,
    "business": None,
    "enterprise": None,
}

AGENT_CONFIG_LIMIT: dict[str, int | None] = {
    "basic": 1,
    "pro": 5,
    "business": None,
    "enterprise": None,
}

FEED_LIMIT: dict[str, int | None] = {
    "basic": 0,
    "pro": 2,
    "business": None,
    "enterprise": None,
}

# Managed agent templates require Business+
MANAGED_AGENT_MIN_TIER = "business"

# TTS availability
TTS_PROVIDER_BY_TIER: dict[str, str | None] = {
    "basic": None,
    "pro": "kutana",
    "business": "premium",
    "enterprise": "premium",
}

# API key access (custom integrations) requires Business+
API_KEY_MIN_TIER = "business"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tier_rank(tier: str) -> int:
    """Return the ordinal rank of a tier, or -1 if unknown."""
    return TIER_ORDER.get(tier, -1)


def _is_subscription_active(user: UserORM) -> bool:
    """A user can consume features if active or still in trial."""
    return user.subscription_status in ("active", "trialing")


def require_tier(user: UserORM, minimum_tier: str) -> None:
    """Raise 403 if the user's plan is below the minimum tier.

    Args:
        user: The authenticated user.
        minimum_tier: One of basic/pro/business/enterprise.

    Raises:
        HTTPException: 402 if subscription is not active/trialing.
        HTTPException: 403 if plan is below the minimum tier.
    """
    if not _is_subscription_active(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription required — please update your billing details.",
        )
    if _tier_rank(user.plan_tier) < _tier_rank(minimum_tier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"This feature requires the {minimum_tier.capitalize()} plan "
                f"or higher. Current plan: {user.plan_tier.capitalize()}."
            ),
        )


def _maybe_reset_cycle(user: UserORM) -> None:
    """Reset monthly usage if the billing cycle has rolled over.

    Acts in-memory on the passed UserORM; caller must flush/commit.
    Uses `billing_cycle_start` — rolls over 30 days after the last reset.
    """
    now = datetime.now(tz=UTC)
    if user.billing_cycle_start is None:
        user.billing_cycle_start = now
        user.meetings_this_month = 0
        return
    elapsed = now - user.billing_cycle_start
    if elapsed.days >= 30:
        user.billing_cycle_start = now
        user.meetings_this_month = 0


async def check_meeting_limit(user: UserORM, db: AsyncSession) -> None:
    """Raise 403 if the user has hit their monthly meeting cap.

    Side effect: resets the cycle counter if 30+ days have elapsed.
    Does NOT increment the counter — callers do that after creation.
    """
    if not _is_subscription_active(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription required — please update your billing details.",
        )
    _maybe_reset_cycle(user)
    limit = MEETINGS_PER_MONTH.get(user.plan_tier)
    if limit is not None and user.meetings_this_month >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Monthly meeting limit reached ({limit} on "
                f"{user.plan_tier.capitalize()} plan). Upgrade for more."
            ),
        )
    # Flush any cycle-reset changes.
    await db.flush()


async def check_agent_config_limit(user: UserORM, db: AsyncSession) -> None:
    """Raise 403 if the user would exceed their agent config limit."""
    if not _is_subscription_active(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription required — please update your billing details.",
        )
    limit = AGENT_CONFIG_LIMIT.get(user.plan_tier)
    if limit is None:
        return
    result = await db.execute(
        select(func.count())
        .select_from(AgentConfigORM)
        .where(AgentConfigORM.owner_id == user.id)
    )
    count = result.scalar_one()
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Custom agent limit reached ({limit} on "
                f"{user.plan_tier.capitalize()} plan). Upgrade for more."
            ),
        )


async def check_feed_limit(user: UserORM, db: AsyncSession) -> None:
    """Raise 403 if the user would exceed their feed-integration limit."""
    if not _is_subscription_active(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription required — please update your billing details.",
        )
    limit = FEED_LIMIT.get(user.plan_tier)
    if limit == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Feed integrations require the Pro plan or higher. "
                f"Current plan: {user.plan_tier.capitalize()}."
            ),
        )
    if limit is None:
        return
    result = await db.execute(
        select(func.count())
        .select_from(FeedORM)
        .where(FeedORM.user_id == user.id)
    )
    count = result.scalar_one()
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Feed integration limit reached ({limit} on "
                f"{user.plan_tier.capitalize()} plan). Upgrade for more."
            ),
        )
