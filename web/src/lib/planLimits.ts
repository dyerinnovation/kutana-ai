/**
 * Frontend-side tier limit definitions — mirrors
 * services/api-server/src/api_server/billing_deps.py.
 *
 * These are used for UI gating (disabling buttons, showing upgrade
 * prompts). The backend is the authoritative enforcement point.
 */

import type { User } from "@/types";

export type PlanTier = "basic" | "pro" | "business" | "enterprise";

const TIER_ORDER: Record<PlanTier, number> = {
  basic: 0,
  pro: 1,
  business: 2,
  enterprise: 3,
};

export const MEETINGS_PER_MONTH: Record<PlanTier, number | null> = {
  basic: 10,
  pro: null,
  business: null,
  enterprise: null,
};

export const AGENT_CONFIG_LIMIT: Record<PlanTier, number | null> = {
  basic: 3,
  pro: 10,
  business: null,
  enterprise: null,
};

export const FEED_LIMIT: Record<PlanTier, number | null> = {
  basic: 2,
  pro: 10,
  business: null,
  enterprise: null,
};

/** Monthly time budgets in minutes */
export const AGENT_MINUTES_PER_MONTH: Record<PlanTier, number | null> = {
  basic: 60,
  pro: 600,
  business: null, // unlimited
  enterprise: null,
};

export const FEED_MINUTES_PER_MONTH: Record<PlanTier, number | null> = {
  basic: 30,
  pro: 300,
  business: null, // unlimited
  enterprise: null,
};

export const MANAGED_AGENT_MIN_TIER: PlanTier = "basic";
export const API_KEY_MIN_TIER: PlanTier = "basic";

export function tierRank(tier: string): number {
  return TIER_ORDER[tier as PlanTier] ?? -1;
}

export function meetsTier(user: User | null, min: PlanTier): boolean {
  if (!user) return false;
  return tierRank(user.plan_tier) >= tierRank(min);
}

export function isSubscriptionActive(user: User | null): boolean {
  if (!user) return false;
  return (
    user.subscription_status === "active" ||
    user.subscription_status === "trialing"
  );
}

export function planLabel(tier: string): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}

/** Returns the tier a user needs to upgrade to in order to use a feature. */
export function upgradeTargetFor(
  feature: "feeds" | "managed-agents" | "api-keys" | "more-feeds" | "more-agents",
): PlanTier {
  if (feature === "more-feeds" || feature === "more-agents") return "pro";
  return "basic";
}
