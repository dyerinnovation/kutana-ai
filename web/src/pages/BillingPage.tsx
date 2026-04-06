import { useEffect, useState } from "react";
import {
  createPortalSession,
  getSubscription,
  type SubscriptionResponse,
} from "@/api/billing";
import {
  AGENT_MINUTES_PER_MONTH,
  FEED_MINUTES_PER_MONTH,
  type PlanTier,
} from "@/lib/planLimits";

const TIER_LABELS: Record<string, string> = {
  basic: "Basic",
  pro: "Pro",
  business: "Business",
  enterprise: "Enterprise",
};

const STATUS_BADGES: Record<
  string,
  { label: string; className: string }
> = {
  trialing: {
    label: "Trial",
    className: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  },
  active: {
    label: "Active",
    className: "bg-green-500/15 text-green-300 border-green-500/30",
  },
  past_due: {
    label: "Past Due",
    className: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  },
  canceled: {
    label: "Canceled",
    className: "bg-gray-500/15 text-gray-300 border-gray-500/30",
  },
  incomplete: {
    label: "Incomplete",
    className: "bg-red-500/15 text-red-300 border-red-500/30",
  },
};

function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

export function BillingPage() {
  const [sub, setSub] = useState<SubscriptionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSubscription()
      .then(setSub)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load"),
      )
      .finally(() => setLoading(false));
  }, []);

  async function openPortal() {
    setPortalLoading(true);
    setError(null);
    try {
      const session = await createPortalSession();
      window.location.href = session.url;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not open billing portal",
      );
      setPortalLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="text-gray-400">Loading billing information…</div>
    );
  }

  if (error || !sub) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-red-300">
        {error ?? "Could not load billing information"}
      </div>
    );
  }

  const badge = STATUS_BADGES[sub.subscription_status] ?? STATUS_BADGES.incomplete;
  const trialDaysLeft =
    sub.subscription_status === "trialing" ? daysUntil(sub.trial_ends_at) : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-50">Billing</h1>
        <p className="mt-1 text-sm text-gray-400">
          Manage your Kutana subscription and billing details.
        </p>
      </div>

      {/* Current plan card */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-50">
                {TIER_LABELS[sub.plan_tier] ?? sub.plan_tier}
              </h2>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${badge.className}`}
              >
                {badge.label}
              </span>
            </div>
            {trialDaysLeft !== null && (
              <p className="mt-2 text-sm text-blue-300">
                Trial ends in {trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"}
                {sub.trial_ends_at &&
                  ` (${new Date(sub.trial_ends_at).toLocaleDateString()})`}
              </p>
            )}
            {sub.subscription_period_end && sub.subscription_status === "active" && (
              <p className="mt-2 text-sm text-gray-400">
                Renews{" "}
                {new Date(sub.subscription_period_end).toLocaleDateString()}
              </p>
            )}
            {sub.subscription_status === "past_due" && (
              <p className="mt-2 text-sm text-yellow-300">
                Payment failed. Please update your billing details.
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            {sub.has_payment_method ? (
              <button
                type="button"
                onClick={openPortal}
                disabled={portalLoading}
                className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-100 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {portalLoading ? "Opening…" : "Manage Subscription"}
              </button>
            ) : (
              <a
                href="/pricing"
                className="rounded-lg bg-blue-600 px-4 py-2 text-center text-sm font-medium text-white transition-colors hover:bg-blue-500"
              >
                Choose a Plan
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Usage card */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <h2 className="text-lg font-semibold text-gray-50">Usage this cycle</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Stat label="Meetings" value={sub.meetings_this_month.toString()} />
          <Stat
            label="Plan"
            value={TIER_LABELS[sub.plan_tier] ?? sub.plan_tier}
          />
        </div>
      </div>

      {/* Time-based usage — TODO: wire to GET /api/billing/usage once the endpoint exists */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-6">
        <h2 className="text-lg font-semibold text-gray-50">Usage This Month</h2>
        <div className="mt-4 space-y-5">
          <UsageMeter
            label="Agent time"
            usedMinutes={0}
            limitMinutes={AGENT_MINUTES_PER_MONTH[(sub.plan_tier as PlanTier) ?? "basic"]}
          />
          <UsageMeter
            label="Feed time"
            usedMinutes={0}
            limitMinutes={FEED_MINUTES_PER_MONTH[(sub.plan_tier as PlanTier) ?? "basic"]}
          />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-gray-50">{value}</div>
    </div>
  );
}

function UsageMeter({
  label,
  usedMinutes,
  limitMinutes,
}: {
  label: string;
  usedMinutes: number;
  limitMinutes: number | null;
}) {
  const isUnlimited = limitMinutes === null;
  const pct = isUnlimited ? 0 : Math.min(100, (usedMinutes / limitMinutes) * 100);

  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-300">{label}</span>
        <span className="text-gray-400">
          {isUnlimited
            ? "Unlimited"
            : `${usedMinutes} / ${limitMinutes} minutes used`}
        </span>
      </div>
      {!isUnlimited && (
        <div className="mt-1.5 h-2 w-full rounded-full bg-gray-800">
          <div
            className={`h-2 rounded-full transition-all ${
              pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-yellow-500" : "bg-green-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
