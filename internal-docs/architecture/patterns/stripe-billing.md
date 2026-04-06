# Stripe Billing Pattern

Kutana uses Stripe for subscription billing with four tiers: Basic, Pro, Business, Enterprise.

## Architecture

```
Browser → PricingSection → createCheckoutSession() → api-server → Stripe Checkout
                                                                       ↓
Stripe Dashboard ← webhook events ← Stripe → api-server /v1/billing/webhook
                                                    ↓
                                              Update user: plan_tier, subscription_status
```

### Key files

| File | Purpose |
|------|---------|
| `services/api-server/src/api_server/routes/billing.py` | Checkout, portal, webhook endpoints |
| `services/api-server/src/api_server/billing_deps.py` | Tier enforcement (require_tier, check limits) |
| `packages/kutana-core/src/kutana_core/database/models.py` | User billing fields (plan_tier, stripe_customer_id, etc.) |
| `web/src/api/billing.ts` | Frontend billing API client |
| `web/src/pages/BillingPage.tsx` | Billing settings UI |
| `web/src/lib/planLimits.ts` | Frontend tier limit mirrors |
| `web/src/components/UpgradeBadge.tsx` | Upgrade prompt component |
| `scripts/stripe_setup.py` | Idempotent Stripe product/price creation |

### User model billing fields

Added via Alembic migration on `users` table:

- `plan_tier` — Enum (basic, pro, business, enterprise), default basic
- `stripe_customer_id` — Stripe customer ID, nullable
- `stripe_subscription_id` — Stripe subscription ID, nullable
- `subscription_status` — Enum (active, past_due, canceled, trialing, incomplete)
- `subscription_period_end` — When the current billing period ends
- `trial_ends_at` — When the trial expires
- `meetings_this_month` — Counter, reset on billing cycle
- `billing_cycle_start` — Start of current billing cycle

## Tier enforcement

Backend enforcement lives in `billing_deps.py`. Three dependency functions:

- `require_tier(user, minimum_tier)` — Raises 402 if subscription not active/trialing, 403 if tier too low
- `check_meeting_limit(user, db)` — Checks monthly meeting cap, auto-resets after 30-day cycle
- `check_agent_config_limit(user, db)` / `check_feed_limit(user, db)` — Count existing resources

Applied at:
- `POST /v1/meetings` — meeting limit
- `POST /v1/agents` — agent config limit
- `POST /v1/feeds` — feed limit
- `POST /v1/agent-templates/.../activate` — managed agent tier check
- `POST /v1/agent-keys` — API key tier check

Frontend mirrors these limits in `planLimits.ts` for UI gating (disabling buttons, showing UpgradeBadge). The backend is always the authoritative enforcement point.

## Webhook events handled

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Set plan_tier, stripe IDs, status=active |
| `customer.subscription.updated` | Update status, period_end, handle plan changes |
| `customer.subscription.deleted` | Set plan_tier=basic, status=canceled |
| `invoice.payment_failed` | Set status=past_due |
| `invoice.paid` | Reset meetings_this_month on new cycle |

## Environment variables

All in Helm secrets (`charts/kutana/values-secrets.yaml`):

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_BASIC_MONTHLY`, `STRIPE_PRICE_BASIC_YEARLY`
- `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_YEARLY`
- `STRIPE_PRICE_BUSINESS_MONTHLY`, `STRIPE_PRICE_BUSINESS_YEARLY`

## Dev testing

Use the `/stripe-webhook` skill to start a local Stripe CLI forwarder that sends test events to the DGX api-server. See `.claude/skills/stripe-webhook/SKILL.md`.

For production: register `https://api-dev.kutana.ai/v1/billing/webhook` in the Stripe dashboard.
