"""Billing endpoints: Stripe Checkout, Customer Portal, and webhooks.

Tier model
----------
Kutana has no free tier. Every user starts on a 14-day trial of the Basic
plan with a credit card on file. If the user does not cancel before the
trial ends, Stripe automatically charges for the first billing period.

Endpoints
---------
- ``POST /v1/billing/create-checkout-session`` — start a Stripe Checkout
  session for a selected plan tier and interval.
- ``POST /v1/billing/create-portal-session`` — open the Stripe Customer
  Portal so the user can manage their subscription.
- ``GET /v1/billing/subscription`` — read the authenticated user's
  subscription details.
- ``POST /v1/billing/webhook`` — Stripe webhook handler (no auth; signature
  verified).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — runtime dep for FastAPI DI

from api_server.auth_deps import CurrentUser  # noqa: TC001 — runtime dep for FastAPI DI
from api_server.deps import Settings, get_db_session, get_settings
from kutana_core.database.models import UsageRecordORM, UserORM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

PlanTier = Literal["basic", "pro", "business", "enterprise"]
BillingInterval = Literal["monthly", "yearly"]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CheckoutSessionRequest(BaseModel):
    """Request body for creating a Checkout session.

    Attributes:
        plan_tier: Target plan tier (basic, pro, business, enterprise).
        interval: Billing interval (monthly or yearly).
    """

    plan_tier: PlanTier
    interval: BillingInterval = "monthly"


class CheckoutSessionResponse(BaseModel):
    """Response containing the Stripe Checkout URL.

    Attributes:
        url: Redirect the browser to this URL to start checkout.
        session_id: The Stripe Checkout session ID.
    """

    url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    """Response containing the Stripe Customer Portal URL.

    Attributes:
        url: Redirect the browser to this URL to manage the subscription.
    """

    url: str


class SubscriptionResponse(BaseModel):
    """Authenticated user's current subscription state.

    Attributes:
        plan_tier: Current plan tier.
        subscription_status: Current subscription status.
        trial_ends_at: Trial expiration, if on a trial.
        subscription_period_end: End of current billing period.
        meetings_this_month: Meeting count for current billing cycle.
        has_payment_method: Whether a Stripe customer exists.
    """

    plan_tier: str
    subscription_status: str
    trial_ends_at: datetime | None
    subscription_period_end: datetime | None
    meetings_this_month: int
    has_payment_method: bool


class UsageBreakdown(BaseModel):
    """Usage data for a single resource type in a billing period.

    Attributes:
        resource_type: "agent" or "feed".
        billing_period: Period string in YYYY-MM format.
        total_seconds: Total usage in seconds.
        total_minutes: Total usage in minutes (convenience field).
        record_count: Number of individual usage records.
    """

    resource_type: str
    billing_period: str
    total_seconds: int
    total_minutes: float
    record_count: int


class UsageResponse(BaseModel):
    """Aggregated usage data for the authenticated user.

    Attributes:
        billing_period: The billing period these records cover (YYYY-MM).
        breakdowns: Per-resource-type usage breakdowns.
        meetings_this_month: Meeting count for the current billing cycle.
    """

    billing_period: str
    breakdowns: list[UsageBreakdown]
    meetings_this_month: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _configure_stripe(settings: Settings) -> None:
    """Configure the Stripe client from settings.

    Args:
        settings: Application settings containing the Stripe secret key.

    Raises:
        HTTPException: 503 if Stripe is not configured.
    """
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured",
        )
    stripe.api_key = settings.stripe_secret_key


def _price_id_for(settings: Settings, plan_tier: PlanTier, interval: BillingInterval) -> str:
    """Resolve the Stripe Price ID for a plan/interval combination.

    Args:
        settings: Application settings with price IDs.
        plan_tier: The plan tier.
        interval: Monthly or yearly.

    Returns:
        The Stripe Price ID.

    Raises:
        HTTPException: 400 if the plan/interval is not available.
    """
    if plan_tier == "enterprise":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enterprise plans require a custom sales contract",
        )

    mapping: dict[tuple[str, str], str] = {
        ("basic", "monthly"): settings.stripe_price_basic_monthly,
        ("basic", "yearly"): settings.stripe_price_basic_yearly,
        ("pro", "monthly"): settings.stripe_price_pro_monthly,
        ("pro", "yearly"): settings.stripe_price_pro_yearly,
        ("business", "monthly"): settings.stripe_price_business_monthly,
        ("business", "yearly"): settings.stripe_price_business_yearly,
    }
    price_id = mapping.get((plan_tier, interval), "")
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Price for {plan_tier}/{interval} is not configured",
        )
    return price_id


async def _ensure_stripe_customer(user: UserORM) -> str:
    """Return the user's Stripe customer ID, creating one if needed.

    Args:
        user: The authenticated user. Mutated to store the new customer ID.

    Returns:
        The Stripe customer ID for this user.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = await stripe.Customer.create_async(
        email=user.email,
        name=user.name,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    return customer.id


def _plan_tier_from_price(settings: Settings, price_id: str) -> str | None:
    """Reverse-lookup the plan tier for a Stripe Price ID.

    Args:
        settings: Application settings with price IDs.
        price_id: The Stripe Price ID to resolve.

    Returns:
        The plan tier string, or None if no match.
    """
    lookup: dict[str, str] = {
        settings.stripe_price_basic_monthly: "basic",
        settings.stripe_price_basic_yearly: "basic",
        settings.stripe_price_pro_monthly: "pro",
        settings.stripe_price_pro_yearly: "pro",
        settings.stripe_price_business_monthly: "business",
        settings.stripe_price_business_yearly: "business",
    }
    return lookup.get(price_id)


def _ts_to_datetime(ts: int | None) -> datetime | None:
    """Convert a Stripe unix timestamp to a timezone-aware datetime.

    Args:
        ts: Unix timestamp in seconds, or None.

    Returns:
        The datetime or None.
    """
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for the authenticated user.

    Starts a subscription with a ``stripe_trial_days``-day trial. The user's
    credit card is collected up front. Stripe sends
    ``customer.subscription.trial_will_end`` three days before the trial
    ends.

    Args:
        body: Plan tier and interval.
        current_user: Authenticated user (from JWT).
        settings: Application settings.

    Returns:
        The Checkout session URL and ID.

    Raises:
        HTTPException: 400 for invalid tier/interval, 503 if Stripe is
            not configured.
    """
    _configure_stripe(settings)
    price_id = _price_id_for(settings, body.plan_tier, body.interval)
    customer_id = await _ensure_stripe_customer(current_user)

    # Only attach a trial if the user has never had a paid subscription.
    subscription_data: dict[str, object] = {
        "metadata": {
            "user_id": str(current_user.id),
            "plan_tier": body.plan_tier,
        },
    }
    if current_user.stripe_subscription_id is None:
        subscription_data["trial_period_days"] = settings.stripe_trial_days

    session = await stripe.checkout.Session.create_async(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        payment_method_collection="always",
        subscription_data=subscription_data,
        client_reference_id=str(current_user.id),
        allow_promotion_codes=True,
    )

    if session.url is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe did not return a checkout URL",
        )
    return CheckoutSessionResponse(url=session.url, session_id=session.id)


@router.post("/create-portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PortalSessionResponse:
    """Create a Stripe Customer Portal session for subscription management.

    Args:
        current_user: Authenticated user.
        settings: Application settings.

    Returns:
        The portal URL.

    Raises:
        HTTPException: 400 if the user has no Stripe customer, 503 if
            Stripe is not configured.
    """
    _configure_stripe(settings)
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account on file — complete checkout first",
        )

    session = await stripe.billing_portal.Session.create_async(
        customer=current_user.stripe_customer_id,
        return_url=settings.billing_portal_return_url,
    )
    return PortalSessionResponse(url=session.url)


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(current_user: CurrentUser) -> SubscriptionResponse:
    """Return the authenticated user's current subscription.

    Args:
        current_user: Authenticated user.

    Returns:
        The subscription state.
    """
    return SubscriptionResponse(
        plan_tier=current_user.plan_tier,
        subscription_status=current_user.subscription_status,
        trial_ends_at=current_user.trial_ends_at,
        subscription_period_end=current_user.subscription_period_end,
        meetings_this_month=current_user.meetings_this_month,
        has_payment_method=current_user.stripe_customer_id is not None,
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    period: str | None = None,
) -> UsageResponse:
    """Return aggregated usage data for the authenticated user.

    Groups :class:`~kutana_core.database.models.UsageRecordORM` records by
    ``resource_type`` for the requested billing period.

    Args:
        current_user: Authenticated user.
        db: Database session.
        period: Billing period in ``YYYY-MM`` format. Defaults to the
            current month.

    Returns:
        Aggregated usage breakdowns and meeting count.
    """
    if period is None:
        period = datetime.now(tz=UTC).strftime("%Y-%m")

    rows = (
        await db.execute(
            select(
                UsageRecordORM.resource_type,
                UsageRecordORM.billing_period,
                func.coalesce(func.sum(UsageRecordORM.duration_seconds), 0).label("total_seconds"),
                func.count().label("record_count"),
            )
            .where(
                UsageRecordORM.user_id == current_user.id,
                UsageRecordORM.billing_period == period,
            )
            .group_by(UsageRecordORM.resource_type, UsageRecordORM.billing_period)
        )
    ).all()

    breakdowns = [
        UsageBreakdown(
            resource_type=row.resource_type,
            billing_period=row.billing_period,
            total_seconds=row.total_seconds,
            total_minutes=round(row.total_seconds / 60, 1),
            record_count=row.record_count,
        )
        for row in rows
    ]

    return UsageResponse(
        billing_period=period,
        breakdowns=breakdowns,
        meetings_this_month=current_user.meetings_this_month,
    )


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


async def _user_by_customer_id(db: AsyncSession, customer_id: str) -> UserORM | None:
    """Look up a user by their Stripe customer ID."""
    result = await db.execute(select(UserORM).where(UserORM.stripe_customer_id == customer_id))
    return result.scalar_one_or_none()


async def _apply_subscription(
    db: AsyncSession,
    subscription: stripe.Subscription,
    settings: Settings,
) -> None:
    """Sync a Stripe Subscription object into the UserORM.

    Args:
        db: Database session.
        subscription: The Stripe Subscription to apply.
        settings: Application settings (for price lookup).
    """
    customer_id = (
        subscription.customer
        if isinstance(subscription.customer, str)
        else subscription.customer.id
    )
    user = await _user_by_customer_id(db, customer_id)
    if user is None:
        logger.warning("Stripe webhook references unknown customer %s", customer_id)
        return

    # Resolve plan tier from the first line item's price.
    price_id: str | None = None
    if subscription["items"] and subscription["items"]["data"]:
        price = subscription["items"]["data"][0].get("price")
        if price:
            price_id = price.get("id") if isinstance(price, dict) else price.id
    plan_tier = _plan_tier_from_price(settings, price_id) if price_id else None

    user.stripe_subscription_id = subscription.id
    user.subscription_status = subscription.status
    user.subscription_period_end = _ts_to_datetime(subscription.get("current_period_end"))
    trial_end_ts = subscription.get("trial_end")
    if trial_end_ts is not None:
        user.trial_ends_at = _ts_to_datetime(trial_end_ts)
    if plan_tier is not None:
        user.plan_tier = plan_tier


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, bool]:
    """Handle Stripe webhook events.

    Verifies the Stripe signature and processes subscription lifecycle
    events. Returns ``{"received": True}`` for events handled or ignored;
    raises 400 for invalid signatures.

    Args:
        request: The incoming webhook request.
        settings: Application settings (for webhook secret).
        db: Database session.

    Returns:
        ``{"received": True}`` on success.

    Raises:
        HTTPException: 400 if the signature is missing or invalid,
            503 if Stripe is not configured.
    """
    if not settings.stripe_webhook_secret or not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured",
        )
    stripe.api_key = settings.stripe_secret_key

    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature header",
        )

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        ) from exc

    event_type = event["type"]
    data = event["data"]["object"]
    logger.info("Stripe webhook received: %s", event_type)

    match event_type:
        case "checkout.session.completed":
            # Link the Stripe customer to our user via client_reference_id.
            user_id = data.get("client_reference_id")
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            if user_id and customer_id:
                result = await db.execute(select(UserORM).where(UserORM.id == user_id))
                user = result.scalar_one_or_none()
                if user is not None:
                    user.stripe_customer_id = customer_id
                    if subscription_id:
                        user.stripe_subscription_id = subscription_id

        case (
            "customer.subscription.created"
            | "customer.subscription.updated"
            | "customer.subscription.trial_will_end"
        ):
            await _apply_subscription(db, data, settings)

        case "customer.subscription.deleted":
            customer_id = (
                data.get("customer")
                if isinstance(data.get("customer"), str)
                else data.get("customer", {}).get("id")
            )
            user = await _user_by_customer_id(db, customer_id) if customer_id else None
            if user is not None:
                user.subscription_status = "canceled"
                user.stripe_subscription_id = None
                user.subscription_period_end = _ts_to_datetime(data.get("current_period_end"))

        case "invoice.payment_failed":
            customer_id = data.get("customer")
            user = await _user_by_customer_id(db, customer_id) if customer_id else None
            if user is not None:
                user.subscription_status = "past_due"

        case "invoice.paid":
            customer_id = data.get("customer")
            user = await _user_by_customer_id(db, customer_id) if customer_id else None
            if user is not None:
                user.meetings_this_month = 0
                user.billing_cycle_start = datetime.now(tz=UTC)

        case _:
            logger.debug("Stripe event %s not handled", event_type)

    return {"received": True}
