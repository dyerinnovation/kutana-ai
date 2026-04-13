import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Agent, AgentTemplate } from "@/types";
import { deleteAgent, listAgents } from "@/api/agents";
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
import { Dialog, DialogFooter, DialogTitle } from "@/components/ui/Dialog";
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

  // Delete confirm state
  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteAgent(deleteTarget.id);
      setAgents((prev) => prev.filter((a) => a.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete agent");
    } finally {
      setDeleting(false);
    }
  }

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
              Your AI Agents that join meetings
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
              <div key={agent.id} className="relative">
                <Link to={`/agents/${agent.id}`}>
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
                <button
                  type="button"
                  aria-label={`Delete ${agent.name}`}
                  title="Delete agent"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setDeleteTarget(agent);
                  }}
                  className="absolute right-2 top-2 rounded-md p-1.5 text-gray-500 hover:bg-red-950/40 hover:text-red-400 transition-colors"
                >
                  <TrashIcon />
                </button>
              </div>
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

      <Dialog
        open={deleteTarget !== null}
        onClose={() => {
          if (!deleting) {
            setDeleteTarget(null);
            setDeleteError(null);
          }
        }}
      >
        <DialogTitle>Delete agent?</DialogTitle>
        <p className="text-sm text-gray-400">
          This will permanently delete{" "}
          <span className="font-medium text-gray-50">{deleteTarget?.name}</span>{" "}
          and revoke its API keys. This cannot be undone.
        </p>
        {deleteError && (
          <div className="mt-3 rounded-lg border border-red-800 bg-red-950/50 px-3 py-2 text-sm text-red-400">
            {deleteError}
          </div>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setDeleteTarget(null);
              setDeleteError(null);
            }}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleConfirmDelete}
            disabled={deleting}
            className="bg-red-600 hover:bg-red-500 focus-visible:ring-red-500"
          >
            {deleting ? "Deleting…" : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}

function TrashIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.75} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
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
