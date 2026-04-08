import { apiFetch } from "./client";

export type PlanTier = "basic" | "pro" | "business" | "enterprise";
export type BillingInterval = "monthly" | "yearly";

export interface CheckoutSessionResponse {
  url: string;
  session_id: string;
}

export interface PortalSessionResponse {
  url: string;
}

export interface SubscriptionResponse {
  plan_tier: PlanTier;
  subscription_status:
    | "active"
    | "past_due"
    | "canceled"
    | "trialing"
    | "incomplete";
  trial_ends_at: string | null;
  subscription_period_end: string | null;
  meetings_this_month: number;
  has_payment_method: boolean;
}

export async function createCheckoutSession(
  plan_tier: Exclude<PlanTier, "enterprise">,
  interval: BillingInterval = "monthly",
): Promise<CheckoutSessionResponse> {
  return apiFetch<CheckoutSessionResponse>("/billing/create-checkout-session", {
    method: "POST",
    body: JSON.stringify({ plan_tier, interval }),
  });
}

export async function createPortalSession(): Promise<PortalSessionResponse> {
  return apiFetch<PortalSessionResponse>("/billing/create-portal-session", {
    method: "POST",
  });
}

export async function getSubscription(): Promise<SubscriptionResponse> {
  return apiFetch<SubscriptionResponse>("/billing/subscription");
}

export interface UsageBreakdown {
  resource_type: string;
  billing_period: string;
  total_seconds: number;
  total_minutes: number;
  record_count: number;
}

export interface UsageResponse {
  billing_period: string;
  breakdowns: UsageBreakdown[];
  meetings_this_month: number;
}

export async function getUsage(period?: string): Promise<UsageResponse> {
  const params = period ? `?period=${period}` : "";
  return apiFetch<UsageResponse>(`/billing/usage${params}`);
}
