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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-sm text-gray-400 mt-1">
            Manage your AI agents and their configurations
          </p>
        </div>
        <Link to="/agents/new">
          <Button>Create Agent</Button>
        </Link>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          Loading agents...
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {!isLoading && !error && agents.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-400 mb-4">
              You don&apos;t have any agents yet.
            </p>
            <Link to="/agents/new">
              <Button>Create your first agent</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {agents.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Link key={agent.id} to={`/agents/${agent.id}`}>
              <Card className="transition-colors hover:border-gray-700 cursor-pointer h-full">
                <CardHeader>
                  <CardTitle>{agent.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-400 line-clamp-2 mb-3">
                    {agent.system_prompt || "No system prompt configured"}
                  </p>
                  {agent.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {agent.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="inline-flex items-center rounded-md bg-gray-800 px-2 py-0.5 text-xs font-medium text-gray-300"
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
