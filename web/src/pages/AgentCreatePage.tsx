import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createAgent } from "@/api/agents";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";

const CAPABILITY_OPTIONS = [
  {
    id: "listen",
    label: "Listen to Audio",
    description: "Agent can hear what's said in the meeting",
  },
  {
    id: "voice",
    label: "Speak with Voice",
    description: "Agent can speak using audio",
  },
  {
    id: "text_chat",
    label: "Text Chat",
    description: "Agent can send and read chat messages",
  },
  {
    id: "task_extraction",
    label: "Task Extraction",
    description: "Agent can identify and track action items",
  },
];

export function AgentCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function toggleCapability(cap: string) {
    setCapabilities((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap]
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const agent = await createAgent({
        name,
        system_prompt: systemPrompt,
        capabilities,
      });
      navigate(`/agents/${agent.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create agent"
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      {/* Prebuilt templates callout */}
      <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-gray-200">Use a prebuilt template</p>
          <p className="text-xs text-gray-500 mt-0.5">
            Start with Meeting Summarizer, Action Item Tracker, and more
          </p>
        </div>
        <Link
          to="/templates"
          className="shrink-0 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm font-medium text-gray-300 hover:border-gray-600 hover:text-white transition-colors"
        >
          Browse Templates
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Create New Agent</CardTitle>
          <p className="text-sm text-gray-400">
            Configure an AI agent that can connect to meetings via MCP
          </p>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-6">
            {error && (
              <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            <Input
              label="Agent Name"
              placeholder="e.g., Meeting Assistant"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-300">
                Agent Instructions{" "}
                <span className="font-normal text-gray-500">(optional)</span>
              </label>
              <p className="text-xs text-gray-500">
                Describe what your agent should do in meetings
              </p>
              <textarea
                className="flex min-h-[120px] w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white placeholder:text-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="You are a meeting assistant that tracks action items and commitments..."
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-300">
                Capabilities
              </label>
              <p className="text-xs text-gray-500">
                Select what this agent can do in a meeting
              </p>
              <div className="space-y-2 mt-1">
                {CAPABILITY_OPTIONS.map((cap) => {
                  const isSelected = capabilities.includes(cap.id);
                  return (
                    <button
                      key={cap.id}
                      type="button"
                      onClick={() => toggleCapability(cap.id)}
                      className={`w-full rounded-lg border px-4 py-3 text-left transition-colors ${
                        isSelected
                          ? "border-blue-500 bg-blue-600/10"
                          : "border-gray-700 bg-gray-800/50 hover:border-gray-600"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-medium ${isSelected ? "text-blue-300" : "text-gray-300"}`}>
                          {cap.label}
                        </span>
                        {isSelected && (
                          <span className="ml-2 h-4 w-4 rounded-full bg-blue-500 flex items-center justify-center shrink-0">
                            <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                            </svg>
                          </span>
                        )}
                      </div>
                      <p className={`text-xs mt-0.5 ${isSelected ? "text-blue-400/70" : "text-gray-500"}`}>
                        {cap.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          </CardContent>

          <CardFooter className="gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/")}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Creating..." : "Create Agent"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
