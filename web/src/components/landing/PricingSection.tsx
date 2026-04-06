import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { createCheckoutSession, type PlanTier } from "@/api/billing";

interface PricingTier {
  name: string;
  tier: PlanTier;
  badge?: string;
  monthlyPrice: string;
  yearlyPrice: string;
  monthlyUnit: string;
  yearlyUnit: string;
  description: string;
  minUsers?: string;
  features: string[];
  cta: { label: string; href: string };
  highlighted: boolean;
}

const tiers: PricingTier[] = [
  {
    name: "Basic",
    monthlyPrice: "$7.99",
    yearlyPrice: "$79",
    monthlyUnit: "/ month",
    yearlyUnit: "/ year",
    description: "For individuals exploring AI-powered meetings.",
    features: [
      "3 agent connections",
      "60 min agent time / month",
      "2 feed connections",
      "30 min feed time / month",
      "10 meetings / month",
      "API key access",
    ],
    cta: { label: "Start Free Trial", href: "/register?plan=basic" },
    highlighted: false,
    tier: "basic",
  },
  {
    name: "Pro",
    badge: "Best for Individuals",
    monthlyPrice: "$29",
    yearlyPrice: "$290",
    monthlyUnit: "/ month",
    yearlyUnit: "/ year",
    description: "For power users who run AI meetings daily.",
    features: [
      "10 agent connections",
      "600 min agent time / month",
      "10 feed connections",
      "300 min feed time / month",
      "Unlimited meetings",
      "Priority support",
    ],
    cta: { label: "Start Free Trial", href: "/register?plan=pro" },
    highlighted: false,
    tier: "pro",
  },
  {
    name: "Business",
    badge: "Most Popular",
    monthlyPrice: "$79",
    yearlyPrice: "$790",
    monthlyUnit: "/ user / month",
    yearlyUnit: "/ user / year",
    description: "For teams running AI-powered meetings daily.",
    minUsers: "Minimum 3 users",
    features: [
      "Unlimited agents",
      "Unlimited agent time",
      "Unlimited feeds",
      "Unlimited feed time",
      "Unlimited meetings",
      "Premium TTS voices",
    ],
    cta: { label: "Start Free Trial", href: "/register?plan=business" },
    highlighted: true,
    tier: "business",
  },
  {
    name: "Enterprise",
    monthlyPrice: "$150+",
    yearlyPrice: "Custom",
    monthlyUnit: "/ user / month",
    yearlyUnit: "",
    description: "For organizations with advanced security and scale needs.",
    minUsers: "Minimum 10 users",
    features: [
      "Everything in Business + custom SLA",
    ],
    cta: {
      label: "Contact Sales",
      href: "mailto:sales@kutana.ai",
    },
    highlighted: false,
    tier: "enterprise",
  },
];

export function PricingSection() {
  const [billing, setBilling] = useState<"monthly" | "yearly">("monthly");
  const [loadingTier, setLoadingTier] = useState<PlanTier | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  async function handleTierClick(tier: PricingTier) {
    setError(null);
    // Not logged in → send to registration with the tier pre-selected.
    if (!user) {
      navigate(`/register?plan=${tier.tier}&interval=${billing}`);
      return;
    }
    // Enterprise never uses checkout.
    if (tier.tier === "enterprise") {
      window.location.href = tier.cta.href;
      return;
    }
    setLoadingTier(tier.tier);
    try {
      const session = await createCheckoutSession(tier.tier, billing);
      window.location.href = session.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout");
      setLoadingTier(null);
    }
  }

  return (
    <section id="pricing" className="relative py-24 bg-slate-950">
      <div className="max-w-7xl mx-auto px-6">
        {/* Section heading */}
        <h2 className="text-3xl md:text-4xl font-bold text-center text-white mb-4">
          Simple, Transparent Pricing
        </h2>
        <p className="text-center text-white/60 max-w-2xl mx-auto mb-10">
          Every plan starts with a 14-day free trial. Credit card required —
          cancel any time before the trial ends.
        </p>
        {error && (
          <div className="mx-auto mb-6 max-w-md rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-center text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Billing toggle */}
        <div className="flex items-center justify-center gap-3 mb-14">
          <span
            className={`text-sm font-medium transition-colors duration-300 ${
              billing === "monthly" ? "text-white" : "text-white/40"
            }`}
          >
            Monthly
          </span>
          <button
            onClick={() =>
              setBilling((b) => (b === "monthly" ? "yearly" : "monthly"))
            }
            className="relative w-14 h-7 rounded-full bg-white/10 border border-white/20 transition-colors duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-green-500"
            aria-label="Toggle billing period"
          >
            <span
              className={`absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-green-500 shadow-md transition-transform duration-300 ${
                billing === "yearly" ? "translate-x-7" : "translate-x-0"
              }`}
            />
          </button>
          <span
            className={`text-sm font-medium transition-colors duration-300 ${
              billing === "yearly" ? "text-white" : "text-white/40"
            }`}
          >
            Yearly
          </span>
          <span className="ml-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/20">
            Save 17%
          </span>
        </div>

        {/* Pricing cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative flex flex-col rounded-2xl border p-7 transition-all duration-300 ${
                tier.highlighted
                  ? "border-green-500/50 bg-gradient-to-b from-green-950/30 to-transparent shadow-[0_0_32px_rgba(34,197,94,0.1)]"
                  : "border-white/10 bg-white/5"
              }`}
            >
              {/* Badge */}
              {tier.badge && (
                <div
                  className={`absolute -top-3 left-1/2 -translate-x-1/2 text-xs font-semibold px-4 py-1 rounded-full ${
                    tier.highlighted
                      ? "bg-green-600 text-white"
                      : "bg-teal-500/20 text-teal-400 border border-teal-500/30"
                  }`}
                >
                  {tier.badge}
                </div>
              )}

              {/* Tier name */}
              <h3 className="text-xl font-bold text-white mt-2 mb-3">
                {tier.name}
              </h3>

              {/* Price */}
              <div className="mb-1">
                <span className="text-4xl font-extrabold text-white">
                  {billing === "monthly"
                    ? tier.monthlyPrice
                    : tier.yearlyPrice}
                </span>
                <span className="text-white/40 text-sm ml-1">
                  {billing === "monthly"
                    ? tier.monthlyUnit
                    : tier.yearlyUnit}
                </span>
              </div>

              {/* Description */}
              <p className="text-white/50 text-sm mb-2">{tier.description}</p>

              {/* Min users */}
              {tier.minUsers && (
                <p className="text-yellow-500/80 text-xs font-medium mb-4">
                  {tier.minUsers}
                </p>
              )}

              {/* Features */}
              <ul className="flex-1 space-y-2.5 mb-8 mt-4">
                {tier.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2 text-sm text-white/70"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      className="w-4 h-4 mt-0.5 flex-shrink-0 text-green-500"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button
                type="button"
                onClick={() => handleTierClick(tier)}
                disabled={loadingTier !== null}
                className={`block w-full text-center py-3 px-4 rounded-xl text-sm font-semibold transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-60 ${
                  tier.highlighted
                    ? "bg-green-600 text-white hover:bg-green-500 shadow-lg shadow-green-600/20"
                    : "bg-white/10 text-white hover:bg-white/15 border border-white/10"
                }`}
              >
                {loadingTier === tier.tier ? "Redirecting…" : tier.cta.label}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default PricingSection;
