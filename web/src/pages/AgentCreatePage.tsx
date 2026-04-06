import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createAgent } from "@/api/agents";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";

const CAPABILITY_OPTIONS = [
  {
    id: "text_only",
    label: "Text Only",
    description: "Agent can read transcripts and send messages but won't be able to speak",
  },
  {
    id: "text_tts",
    label: "Text + Kutana Text-to-Speech (TTS)",
    description: "Agent is Text only but will use Kutana TTS to speak",
  },
  {
    id: "voice",
    label: "Voice Agent",
    description: "Agent has full voice capabilities and will listen to the meeting audio stream directly",
  },
];

export function AgentCreatePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [capability, setCapability] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const agent = await createAgent({ name, capabilities: [capability] });
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
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Create New Agent</CardTitle>
          <p className="text-sm text-gray-400">
            Register a custom agent that connects to meetings via MCP. Declare what it can do — Kutana handles the rest.
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
                Select your agent's capability
              </label>
              <p className="text-xs text-gray-500">
                Choose how this agent interacts in meetings
              </p>
              <div className="space-y-2 mt-1">
                {CAPABILITY_OPTIONS.map((cap) => {
                  const isSelected = cap.id === capability;
                  return (
                    <button
                      key={cap.id}
                      type="button"
                      onClick={() => setCapability(cap.id)}
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
                        <span className={`ml-2 h-4 w-4 shrink-0 rounded-full border-2 flex items-center justify-center ${
                          isSelected
                            ? "border-blue-500"
                            : "border-gray-600"
                        }`}>
                          {isSelected && (
                            <span className="h-2 w-2 rounded-full bg-blue-500" />
                          )}
                        </span>
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

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="text-lg">Connect to Kutana</CardTitle>
          <p className="text-sm text-gray-400">
            After creating your agent, follow these steps to connect it
          </p>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4 text-sm">
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-xs font-medium text-blue-400">1</span>
              <div>
                <p className="font-medium text-gray-200">Create your API Key</p>
                <p className="text-gray-500 mt-0.5">Generate an API key from your agent's detail page after creation</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-xs font-medium text-blue-400">2</span>
              <div>
                <p className="font-medium text-gray-200">Connect following the documentation for your agent</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Link to="/docs" className="rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-1.5 text-xs font-medium text-gray-300 hover:border-gray-600 hover:text-gray-50 transition-colors">
                    Claude Code
                  </Link>
                  <Link to="/docs" className="rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-1.5 text-xs font-medium text-gray-300 hover:border-gray-600 hover:text-gray-50 transition-colors">
                    OpenClaw
                  </Link>
                  <Link to="/docs" className="rounded-lg border border-gray-700 bg-gray-800/50 px-3 py-1.5 text-xs font-medium text-gray-300 hover:border-gray-600 hover:text-gray-50 transition-colors">
                    Other Agents
                  </Link>
                </div>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-xs font-medium text-blue-400">3</span>
              <div>
                <p className="font-medium text-gray-200">Tell or schedule your agent to call in to the meeting</p>
                <p className="text-gray-500 mt-0.5">Your agent can join any meeting you create or are invited to</p>
              </div>
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
