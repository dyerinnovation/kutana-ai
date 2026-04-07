import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Agent, AgentTemplate } from "@/types";
import { listAgents } from "@/api/agents";
import { listTemplates } from "@/api/agentTemplates";
import { formatCapability } from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { ActivateTemplateDialog } from "@/components/ActivateTemplateDialog";
import { useAuth } from "@/hooks/useAuth";
import { AGENT_CONFIG_LIMIT, meetsTier, planLabel } from "@/lib/planLimits";
import { UpgradeBadge } from "@/components/UpgradeBadge";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "productivity", label: "Productivity" },
  { value: "engineering", label: "Engineering" },
  { value: "general", label: "General" },
];

const CATEGORY_COLORS: Record<string, string> = {
  productivity: "bg-blue-600/20 text-blue-400 border border-blue-500/30",
  engineering: "bg-cyan-600/20 text-cyan-400 border border-cyan-500/30",
  general: "bg-gray-600/20 text-gray-400 border border-gray-500/30",
};

export function AgentsPage() {
  const { user } = useAuth();
  const agentLimit = user
    ? AGENT_CONFIG_LIMIT[user.plan_tier as keyof typeof AGENT_CONFIG_LIMIT]
    : 0;

  // User agents state
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState<string | null>(null);

  // Templates state
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");

  // Activate modal state
  const [activateTarget, setActivateTarget] = useState<AgentTemplate | null>(null);

  useEffect(() => {
    listAgents()
      .then((res) => setAgents(res.items))
      .catch((err) =>
        setAgentsError(err instanceof Error ? err.message : "Failed to load agents")
      )
      .finally(() => setAgentsLoading(false));
  }, []);

  useEffect(() => {
    setTemplatesLoading(true);
    setTemplatesError(null);
    listTemplates(categoryFilter || undefined)
      .then((data) => setTemplates(data))
      .catch((err) =>
        setTemplatesError(err instanceof Error ? err.message : "Failed to load templates")
      )
      .finally(() => setTemplatesLoading(false));
  }, [categoryFilter]);

  return (
    <div className="space-y-10">
      {/* ── Your Agents ─────────────────────────────────────── */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-gray-50">
              Your Agents
            </h1>
            <p className="mt-0.5 text-sm text-gray-400">
              AI agents that join and listen to your meetings
            </p>
          </div>
          {(() => {
            const atLimit =
              agentLimit !== null && agents.length >= agentLimit;
            if (atLimit) {
              return (
                <div className="flex flex-col items-end gap-1">
                  <Button disabled title={`Limit reached on ${planLabel(user?.plan_tier ?? "basic")} plan`}>
                    <PlusIcon />
                    New Agent
                  </Button>
                  <UpgradeBadge requiredTier={user?.plan_tier === "basic" ? "pro" : "business"} />
                </div>
              );
            }
            return (
              <Link to="/agents/new">
                <Button>
                  <PlusIcon />
                  New Agent
                </Button>
              </Link>
            );
          })()}
        </div>

        {agentsLoading && (
          <div className="flex items-center justify-center py-12 text-sm text-gray-500">
            <SpinnerIcon />
            Loading agents…
          </div>
        )}

        {agentsError && (
          <div className="rounded-lg border border-red-900/60 bg-red-950/50 px-4 py-3 text-sm text-red-400">
            {agentsError}
          </div>
        )}

        {!agentsLoading && !agentsError && agents.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center py-12 text-center">
              <p className="mb-1 text-sm font-medium text-gray-300">No agents yet</p>
              <p className="mb-4 text-sm text-gray-500">
                Create an AI agent to start attending your meetings.
              </p>
              <Link to="/agents/new">
                <Button>Create your first agent</Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {agents.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <Link key={agent.id} to={`/agents/${agent.id}`}>
                <Card className="card-interactive h-full cursor-pointer border-gray-800">
                  <CardHeader>
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600/15 text-sm font-semibold text-blue-400">
                        {agent.name.charAt(0).toUpperCase()}
                      </div>
                      <CardTitle className="pt-0.5">{agent.name}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="mb-3 text-xs font-medium text-gray-400">
                      {agent.capabilities.includes("listen") && agent.capabilities.includes("speak")
                        ? "Voice Agent"
                        : agent.capabilities.includes("speak")
                          ? "Text + Speech (Kutana TTS)"
                          : "Text Only"}
                    </p>
                    {agent.capabilities.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {agent.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="inline-flex items-center rounded-md border border-gray-700 bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400"
                          >
                            {formatCapability(cap)}
                          </span>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* ── Kutana Managed Agents ──────────────────────────── */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-gray-50">
            Kutana Managed Agents
          </h2>
          <p className="mt-0.5 text-sm text-gray-400">
            Prebuilt AI agents you can activate for any meeting
          </p>
        </div>

        {/* Category filter pills */}
        <div className="flex gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setCategoryFilter(cat.value)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                categoryFilter === cat.value
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-50"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {templatesError && (
          <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
            {templatesError}
          </div>
        )}

        {templatesLoading && (
          <div className="flex items-center justify-center py-8 text-sm text-gray-500">
            <SpinnerIcon />
            Loading templates…
          </div>
        )}

        {!templatesLoading && templates.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-gray-400">
                No managed agents found{categoryFilter ? ` in "${categoryFilter}"` : ""}.
              </p>
            </CardContent>
          </Card>
        )}

        {templates.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {templates.map((template) => (
              <Card key={template.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <CardTitle>{template.name}</CardTitle>
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                        CATEGORY_COLORS[template.category] ?? CATEGORY_COLORS.general
                      }`}
                    >
                      {template.category.charAt(0).toUpperCase() + template.category.slice(1)}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-400 mb-3">{template.description}</p>
                  {template.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-4">
                      {template.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="inline-flex rounded-md bg-gray-800 px-2 py-0.5 text-xs text-gray-400"
                        >
                          {formatCapability(cap)}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    {template.is_premium && (
                      meetsTier(user, "pro")
                        ? <span className="inline-flex items-center rounded-md bg-blue-600/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 text-xs font-medium">Pro</span>
                        : <UpgradeBadge requiredTier="pro" />
                    )}
                    {template.is_premium && !meetsTier(user, "pro") ? (
                      <Button size="sm" disabled className="ml-auto" title="Upgrade to Pro to activate">
                        Activate
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => setActivateTarget(template)}
                        className="ml-auto"
                      >
                        Activate
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* ── Feed Agents ─────────────────────────────────── */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-gray-50">
            Feed Agents
          </h2>
          <p className="mt-0.5 text-sm text-gray-400">
            Feed agents automatically pull data from your connected feeds into
            meetings and push meeting insights to external platforms like Slack
            and Discord.
          </p>
        </div>
        <Link to="/feeds">
          <Button variant="outline" size="sm">
            Manage Feeds
          </Button>
        </Link>
      </section>

      <ActivateTemplateDialog
        template={activateTarget}
        onClose={() => setActivateTarget(null)}
      />
    </div>
  );
}

function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg className="mr-2 h-4 w-4 animate-spin text-gray-500" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}
