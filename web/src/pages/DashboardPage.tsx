import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Agent } from "@/types";
import { listAgents } from "@/api/agents";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";

export function DashboardPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents()
      .then((res) => setAgents(res.items))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load agents")
      )
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="space-y-6">

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-gray-50">
            Agents
          </h1>
          <p className="mt-0.5 text-sm text-gray-400">
            AI agents that join and listen to your meetings
          </p>
        </div>
        <Link to="/agents/new">
          <Button>
            <PlusIcon />
            New Agent
          </Button>
        </Link>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20 text-sm text-gray-500">
          <SpinnerIcon />
          Loading agents…
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && agents.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center py-16 text-center">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gray-800">
              <AgentEmptyIcon />
            </div>
            <p className="mb-1 text-sm font-medium text-gray-300">No agents yet</p>
            <p className="mb-6 text-sm text-gray-500">
              Create an AI agent to start attending your meetings.
            </p>
            <Link to="/agents/new">
              <Button>Create your first agent</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Agent grid */}
      {agents.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Link key={agent.id} to={`/agents/${agent.id}`}>
              <Card className="card-interactive h-full cursor-pointer border-gray-800">
                <CardHeader>
                  <div className="flex items-start gap-3">
                    {/* Agent avatar */}
                    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600/15 text-sm font-semibold text-blue-400">
                      {agent.name.charAt(0).toUpperCase()}
                    </div>
                    <CardTitle className="pt-0.5">{agent.name}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="mb-3 line-clamp-2 text-xs text-gray-500 leading-relaxed">
                    {agent.system_prompt || "No system prompt configured"}
                  </p>
                  {agent.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {agent.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="inline-flex items-center rounded-md border border-gray-700 bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400"
                        >
                          {cap}
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

function AgentEmptyIcon() {
  return (
    <svg className="h-6 w-6 text-gray-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 1-6.23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
    </svg>
  );
}
