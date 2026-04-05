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
  basic: 1,
  pro: 5,
  business: null,
  enterprise: null,
};

export const FEED_LIMIT: Record<PlanTier, number | null> = {
  basic: 0,
  pro: 2,
  business: null,
  enterprise: null,
};

export const MANAGED_AGENT_MIN_TIER: PlanTier = "business";
export const API_KEY_MIN_TIER: PlanTier = "business";

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
export function upgradeTargetFor(feature: "feeds" | "managed-agents" | "api-keys"): PlanTier {
  if (feature === "feeds") return "pro";
  return "business";
}
