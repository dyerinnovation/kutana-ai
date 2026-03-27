import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createAgent } from "@/api/agents";
import { formatCapability, CAPABILITY_TOOLTIPS } from "@/lib/capabilities";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";

const CAPABILITY_OPTIONS = [
  "transcription",
  "task_extraction",
  "summarization",
  "action_items",
  "voice",
];

export function AgentCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
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
      const agent = await createAgent({ name, capabilities });
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
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Create New Agent</CardTitle>
          <p className="text-sm text-gray-400">
            Register a custom agent that connects to meetings via MCP. Declare what it can do — Convene handles the rest.
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

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-300">
                Capabilities
              </label>
              <div className="flex flex-wrap gap-2">
                {CAPABILITY_OPTIONS.map((cap) => (
                  <button
                    key={cap}
                    type="button"
                    onClick={() => toggleCapability(cap)}
                    className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                      capabilities.includes(cap)
                        ? "border-blue-500 bg-blue-600/20 text-blue-400"
                        : "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600"
                    }`}
                    title={CAPABILITY_TOOLTIPS[cap] ?? ""}
                  >
                    {formatCapability(cap)}
                  </button>
                ))}
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
