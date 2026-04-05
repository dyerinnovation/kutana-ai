import { Link } from "react-router-dom";
import { planLabel, type PlanTier } from "@/lib/planLimits";

/**
 * Small pill that links to /pricing. Used next to locked features
 * to indicate the tier required to unlock them.
 */
export function UpgradeBadge({ requiredTier }: { requiredTier: PlanTier }) {
  return (
    <Link
      to="/pricing"
      className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-300 transition-colors hover:bg-amber-500/20"
      title={`Requires ${planLabel(requiredTier)} plan or higher`}
    >
      <svg
        className="h-2.5 w-2.5"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2.5}
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
        />
      </svg>
      {planLabel(requiredTier)}
    </Link>
  );
}
