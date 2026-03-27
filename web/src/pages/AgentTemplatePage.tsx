import { useEffect, useState, type FormEvent } from "react";
import type { AgentTemplate, Meeting } from "@/types";
import { listTemplates, activateTemplate } from "@/api/agentTemplates";
import { formatCapability } from "@/lib/capabilities";
import { listMeetings } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "productivity", label: "Productivity" },
  { value: "engineering", label: "Engineering" },
  { value: "general", label: "General" },
];

const CATEGORY_COLORS: Record<string, string> = {
  productivity:
    "bg-blue-600/20 text-blue-400 border border-blue-500/30",
  engineering:
    "bg-cyan-600/20 text-cyan-400 border border-cyan-500/30",
  general:
    "bg-gray-600/20 text-gray-400 border border-gray-500/30",
};

export function AgentTemplatePage() {
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("");

  // Activate modal state
  const [activateTarget, setActivateTarget] = useState<AgentTemplate | null>(
    null
  );
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isActivating, setIsActivating] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, [categoryFilter]);

  async function loadTemplates() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listTemplates(categoryFilter || undefined);
      setTemplates(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load templates"
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function openActivateModal(template: AgentTemplate) {
    setActivateTarget(template);
    setSelectedMeetingId("");
    setApiKey("");
    try {
      const res = await listMeetings();
      setMeetings(
        res.items.filter(
          (m) => m.status === "scheduled" || m.status === "active"
        )
      );
    } catch {
      setMeetings([]);
    }
  }

  async function handleActivate(e: FormEvent) {
    e.preventDefault();
    if (!activateTarget || !selectedMeetingId) return;

    setIsActivating(true);
    setError(null);
    try {
      await activateTemplate(
        activateTarget.id,
        selectedMeetingId,
        apiKey || undefined
      );
      setActivateTarget(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to activate template"
      );
    } finally {
      setIsActivating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Agent Templates</h1>
        <p className="text-sm text-gray-400 mt-1">
          Browse and activate prebuilt AI agents for your meetings
        </p>
      </div>

      {/* Category filter */}
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

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          Loading templates...
        </div>
      )}

      {!isLoading && templates.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-400">
              No templates found{categoryFilter ? ` in "${categoryFilter}"` : ""}.
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
                      CATEGORY_COLORS[template.category] ??
                      CATEGORY_COLORS.general
                    }`}
                  >
                    {template.category.charAt(0).toUpperCase() + template.category.slice(1)}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-400 mb-3">
                  {template.description}
                </p>
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
                    <span className="text-xs text-yellow-400 font-medium">
                      Premium
                    </span>
                  )}
                  <Button
                    size="sm"
                    onClick={() => openActivateModal(template)}
                    className="ml-auto"
                  >
                    Activate
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Activate Dialog */}
      <Dialog
        open={activateTarget !== null}
        onClose={() => setActivateTarget(null)}
      >
        <form onSubmit={handleActivate}>
          <DialogTitle>
            Activate: {activateTarget?.name}
          </DialogTitle>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-300">
                Meeting
              </label>
              {meetings.length === 0 ? (
                <p className="text-sm text-gray-500">
                  No active or scheduled meetings available.
                </p>
              ) : (
                <select
                  className="flex h-10 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-50 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={selectedMeetingId}
                  onChange={(e) => setSelectedMeetingId(e.target.value)}
                  required
                >
                  <option value="">Select a meeting</option>
                  {meetings.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.title} ({m.status})
                    </option>
                  ))}
                </select>
              )}
            </div>
            <Input
              label="Anthropic API Key (optional)"
              type="password"
              placeholder="sk-ant-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <p className="text-xs text-gray-500">
              Provide your own API key for this agent, or leave blank to use
              the platform key.
            </p>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setActivateTarget(null)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isActivating || !selectedMeetingId}
            >
              {isActivating ? "Activating..." : "Activate Agent"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
