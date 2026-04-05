#!/usr/bin/env python3
"""Idempotent Stripe Product + Price bootstrap for Kutana tiers.

Usage
-----
    export STRIPE_SECRET_KEY=sk_test_...
    uv run python scripts/stripe_setup.py

Creates (or reuses) one Product per tier and monthly/yearly Prices for the
paid individual tiers. Emits the resulting Price IDs as environment-variable
lines that can be pasted into ``.env`` or a Helm secret.

Tiers
-----
- Basic:    $7.99 / mo, $79 / yr
- Pro:     $29.00 / mo, $290 / yr
- Business: $79.00 / mo, $790 / yr
- Enterprise: custom — created as a Product only, no Price.

The script uses stable ``lookup_key`` values on each Price so that re-runs
reuse existing records instead of creating duplicates.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import stripe


@dataclass(frozen=True)
class Tier:
    """A Kutana subscription tier."""

    key: str
    name: str
    description: str
    monthly_cents: int | None
    yearly_cents: int | None


TIERS: list[Tier] = [
    Tier(
        key="basic",
        name="Kutana Basic",
        description=(
            "Individual plan with 10 meetings/month, 1 custom agent "
            "connection, and 30-day memory."
        ),
        monthly_cents=799,
        yearly_cents=7900,
    ),
    Tier(
        key="pro",
        name="Kutana Pro",
        description=(
            "Unlimited meetings, 5 custom agent connections, 2 feed "
            "integrations, Kutana TTS, and 90-day memory."
        ),
        monthly_cents=2900,
        yearly_cents=29000,
    ),
    Tier(
        key="business",
        name="Kutana Business",
        description=(
            "Unlimited everything, premium TTS, managed agent credits, "
            "unlimited memory, and full API access."
        ),
        monthly_cents=7900,
        yearly_cents=79000,
    ),
    Tier(
        key="enterprise",
        name="Kutana Enterprise",
        description=(
            "Custom deployment, SSO, dedicated infra, SLAs, and audit "
            "logging. Billed manually."
        ),
        monthly_cents=None,
        yearly_cents=None,
    ),
]

CURRENCY = "usd"


def upsert_product(tier: Tier) -> stripe.Product:
    """Return the existing Product for a tier, or create it.

    Args:
        tier: The tier to upsert.

    Returns:
        The Stripe Product.
    """
    product_id = f"kutana_{tier.key}"
    try:
        product = stripe.Product.retrieve(product_id)
        stripe.Product.modify(
            product_id,
            name=tier.name,
            description=tier.description,
            metadata={"tier": tier.key},
        )
        return product
    except stripe.InvalidRequestError:
        return stripe.Product.create(
            id=product_id,
            name=tier.name,
            description=tier.description,
            metadata={"tier": tier.key},
        )


def upsert_price(
    product: stripe.Product,
    tier_key: str,
    interval: str,
    amount_cents: int,
) -> stripe.Price:
    """Return the Price for (product, interval), creating it if missing.

    Stripe Prices are immutable; we use a stable ``lookup_key`` so re-runs
    find the existing record rather than creating a duplicate.

    Args:
        product: The parent Product.
        tier_key: Plan tier key ("basic" etc.).
        interval: "month" or "year".
        amount_cents: Unit amount in cents.

    Returns:
        The Stripe Price.
    """
    lookup_key = f"kutana_{tier_key}_{interval}ly"
    existing = stripe.Price.list(lookup_keys=[lookup_key], limit=1, active=True)
    if existing.data:
        price = existing.data[0]
        if price.unit_amount == amount_cents:
            return price
        # Amount changed — archive and recreate.
        stripe.Price.modify(price.id, active=False)

    return stripe.Price.create(
        product=product.id,
        unit_amount=amount_cents,
        currency=CURRENCY,
        recurring={"interval": interval},
        lookup_key=lookup_key,
        metadata={"tier": tier_key, "interval": interval},
    )


def main() -> int:
    """Create/update all Kutana products and prices in Stripe.

    Returns:
        Exit code (0 on success).
    """
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not secret_key:
        print(
            "ERROR: STRIPE_SECRET_KEY is not set in the environment.",
            file=sys.stderr,
        )
        return 1
    stripe.api_key = secret_key

    print("Configuring Stripe products and prices...\n")
    env_lines: list[str] = []

    for tier in TIERS:
        product = upsert_product(tier)
        print(f"  Product: {product.id} — {tier.name}")
        if tier.monthly_cents is not None:
            monthly = upsert_price(
                product, tier.key, "month", tier.monthly_cents
            )
            print(f"    monthly: {monthly.id}  (${tier.monthly_cents / 100:.2f})")
            env_lines.append(
                f"STRIPE_PRICE_{tier.key.upper()}_MONTHLY={monthly.id}"
            )
        if tier.yearly_cents is not None:
            yearly = upsert_price(product, tier.key, "year", tier.yearly_cents)
            print(f"    yearly:  {yearly.id}  (${tier.yearly_cents / 100:.2f})")
            env_lines.append(
                f"STRIPE_PRICE_{tier.key.upper()}_YEARLY={yearly.id}"
            )

    print("\nAdd these to your .env file or Helm secret:\n")
    print("\n".join(env_lines))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
