import { useEffect, useState, type FormEvent } from "react";
import type { Feed, FeedCreate } from "@/types";
import { listFeeds, createFeed, updateFeed, toggleFeed, triggerFeed } from "@/api/feeds";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";

const DATA_TYPE_OPTIONS = [
  { value: "summary", label: "Summary" },
  { value: "action_items", label: "Action Items" },
  { value: "decisions", label: "Decisions" },
  { value: "transcript", label: "Transcript" },
  { value: "key_topics", label: "Key Topics" },
];

const CONTEXT_TYPE_OPTIONS = [
  { value: "agenda", label: "Agenda" },
  { value: "participants", label: "Participants" },
  { value: "previous_meetings", label: "Previous Meetings" },
];

const DIRECTION_OPTIONS = [
  { value: "outbound", label: "Outbound" },
  { value: "inbound", label: "Inbound" },
  { value: "bidirectional", label: "Bidirectional" },
] as const;

const TRIGGER_OPTIONS = [
  { value: "meeting_end", label: "When meeting ends" },
  { value: "on_demand", label: "On demand" },
  { value: "scheduled", label: "Scheduled" },
] as const;

interface Integration {
  id: string;
  name: string;
  description: string;
  status: "available" | "coming_soon" | "planned";
  platform: string;
}

const INTEGRATIONS: Integration[] = [
  {
    id: "slack",
    name: "Slack",
    description: "Push meeting summaries, action items, and decisions to Slack channels.",
    status: "available",
    platform: "slack",
  },
  {
    id: "discord",
    name: "Discord",
    description: "Share meeting notes and updates with your Discord server.",
    status: "available",
    platform: "discord",
  },
  {
    id: "notion",
    name: "Notion",
    description: "Automatically create meeting pages with structured notes.",
    status: "planned",
    platform: "notion",
  },
  {
    id: "github",
    name: "GitHub",
    description: "Create issues from action items and link decisions to PRs.",
    status: "planned",
    platform: "github",
  },
];

const STATUS_BADGE: Record<string, string> = {
  available: "bg-green-600/20 text-green-400 border border-green-500/30",
  coming_soon: "bg-yellow-600/20 text-yellow-400 border border-yellow-500/30",
  planned: "bg-gray-600/20 text-gray-400 border border-gray-500/30",
};

const STATUS_LABEL: Record<string, string> = {
  available: "Available",
  coming_soon: "Coming Soon",
  planned: "Planned",
};

const DIRECTION_ARROW: Record<string, string> = {
  outbound: "->",
  inbound: "<-",
  bidirectional: "<->",
};

const PLATFORM_DELIVERY: Record<string, "channel" | "mcp"> = {
  slack: "mcp",
  notion: "mcp",
  github: "mcp",
  discord: "channel",
  telegram: "channel",
  imessage: "channel",
};

const EMPTY_FORM: FeedCreate = {
  name: "",
  platform: "slack",
  direction: "outbound",
  delivery_type: "mcp",
  channel_name: "",
  mcp_server_url: "",
  mcp_auth_token: "",
  data_types: [],
  context_types: [],
  trigger: "meeting_end",
  meeting_tag: "",
};

export function FeedsPage() {
  // Feeds state
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [feedsLoading, setFeedsLoading] = useState(true);
  const [feedsError, setFeedsError] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingFeed, setEditingFeed] = useState<Feed | null>(null);
  const [form, setForm] = useState<FeedCreate>({ ...EMPTY_FORM });
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    loadFeeds();
  }, []);

  function loadFeeds() {
    setFeedsLoading(true);
    setFeedsError(null);
    listFeeds()
      .then((res) => setFeeds(res.items))
      .catch((err) =>
        setFeedsError(err instanceof Error ? err.message : "Failed to load feeds")
      )
      .finally(() => setFeedsLoading(false));
  }

  function openCreateModal(platform: string) {
    setEditingFeed(null);
    setForm({ ...EMPTY_FORM, platform, delivery_type: PLATFORM_DELIVERY[platform] ?? "mcp" });
    setSaveError(null);
    setModalOpen(true);
  }

  function openEditModal(feed: Feed) {
    setEditingFeed(feed);
    setForm({
      name: feed.name,
      platform: feed.platform,
      direction: feed.direction,
      delivery_type: feed.delivery_type,
      mcp_server_url: feed.mcp_server_url ?? "",
      channel_name: feed.channel_name ?? "",
      data_types: [...feed.data_types],
      context_types: [...feed.context_types],
      trigger: feed.trigger,
      meeting_tag: feed.meeting_tag ?? "",
    });
    setSaveError(null);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingFeed(null);
    setSaveError(null);
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setIsSaving(true);
    setSaveError(null);
    try {
      const payload: FeedCreate = {
        ...form,
        mcp_server_url: form.delivery_type === "mcp" ? form.mcp_server_url : undefined,
        mcp_auth_token: form.delivery_type === "mcp" ? form.mcp_auth_token : undefined,
        channel_name: form.delivery_type === "channel" ? form.channel_name : undefined,
        meeting_tag: form.meeting_tag || undefined,
        context_types: form.context_types?.length ? form.context_types : undefined,
      };
      if (editingFeed) {
        await updateFeed(editingFeed.id, payload);
      } else {
        await createFeed(payload);
      }
      closeModal();
      loadFeeds();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save feed");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggle(feed: Feed) {
    try {
      await toggleFeed(feed.id, !feed.is_active);
      loadFeeds();
    } catch (err) {
      setFeedsError(err instanceof Error ? err.message : "Failed to toggle feed");
    }
  }

  async function handleTrigger(feed: Feed) {
    try {
      await triggerFeed(feed.id);
      loadFeeds();
    } catch (err) {
      setFeedsError(err instanceof Error ? err.message : "Failed to trigger feed");
    }
  }

  function toggleDataType(value: string) {
    setForm((prev) => ({
      ...prev,
      data_types: prev.data_types.includes(value)
        ? prev.data_types.filter((d) => d !== value)
        : [...prev.data_types, value],
    }));
  }

  function toggleContextType(value: string) {
    setForm((prev) => ({
      ...prev,
      context_types: (prev.context_types ?? []).includes(value)
        ? (prev.context_types ?? []).filter((c) => c !== value)
        : [...(prev.context_types ?? []), value],
    }));
  }

  return (
    <div className="space-y-10">
      {/* ── Configured Feeds ─────────────────────────────────── */}
      <section className="space-y-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-gray-50">
            Feeds
          </h1>
          <p className="mt-0.5 text-sm text-gray-400">
            Connect meetings to external platforms — push summaries, pull context.
          </p>
        </div>

        {feedsLoading && (
          <div className="flex items-center justify-center py-12 text-sm text-gray-500">
            <SpinnerIcon />
            Loading feeds...
          </div>
        )}

        {feedsError && (
          <div className="rounded-lg border border-red-900/60 bg-red-950/50 px-4 py-3 text-sm text-red-400">
            {feedsError}
          </div>
        )}

        {!feedsLoading && !feedsError && feeds.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center py-12 text-center">
              <p className="mb-1 text-sm font-medium text-gray-300">
                No feeds configured
              </p>
              <p className="mb-4 text-sm text-gray-500">
                Set up an integration below to start pushing meeting data to external
                platforms.
              </p>
            </CardContent>
          </Card>
        )}

        {feeds.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {feeds.map((feed) => (
              <Card
                key={feed.id}
                className={`h-full ${
                  feed.is_active
                    ? "border-gray-800"
                    : "border-gray-800/50 opacity-60"
                }`}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600/15 text-sm font-semibold text-blue-400">
                        {feed.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <CardTitle className="pt-0.5">{feed.name}</CardTitle>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="inline-flex items-center rounded-md bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400 border border-gray-700">
                            {feed.platform}
                          </span>
                          <span className="text-[10px] text-gray-500">
                            {DIRECTION_ARROW[feed.direction] ?? feed.direction}
                          </span>
                          <span className="text-[10px] text-gray-500">
                            {feed.trigger}
                          </span>
                        </div>
                      </div>
                    </div>
                    <span
                      className={`inline-flex h-2 w-2 rounded-full ${
                        feed.is_active ? "bg-green-400" : "bg-gray-600"
                      }`}
                      title={feed.is_active ? "Active" : "Inactive"}
                    />
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Data types */}
                  {feed.data_types.length > 0 && (
                    <div className="mb-3 flex flex-wrap gap-1">
                      {feed.data_types.map((dt) => (
                        <span
                          key={dt}
                          className="inline-flex items-center rounded-md border border-gray-700 bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400"
                        >
                          {dt}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Last triggered / error */}
                  {feed.last_triggered_at && (
                    <p className="mb-1 text-[11px] text-gray-500">
                      Last triggered:{" "}
                      {new Date(feed.last_triggered_at).toLocaleString()}
                    </p>
                  )}
                  {feed.last_error && (
                    <p className="mb-2 rounded border border-red-900/40 bg-red-950/30 px-2 py-1 text-[11px] text-red-400">
                      {feed.last_error}
                    </p>
                  )}

                  {/* Actions */}
                  <div className="mt-3 flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openEditModal(feed)}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleToggle(feed)}
                    >
                      {feed.is_active ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleTrigger(feed)}
                      disabled={!feed.is_active}
                    >
                      Run Now
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* ── Available Integrations ───────────────────────────── */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-gray-50">
            Available Integrations
          </h2>
          <p className="mt-0.5 text-sm text-gray-400">
            Connect Kutana to your favorite platforms
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {INTEGRATIONS.map((integration) => (
            <Card key={integration.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>{integration.name}</CardTitle>
                  <span
                    className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                      STATUS_BADGE[integration.status]
                    }`}
                  >
                    {STATUS_LABEL[integration.status]}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="mb-4 text-sm text-gray-400">
                  {integration.description}
                </p>
                <Button
                  size="sm"
                  onClick={() => openCreateModal(integration.platform)}
                  disabled={integration.status !== "available"}
                >
                  {integration.status === "available"
                    ? "Configure"
                    : STATUS_LABEL[integration.status]}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* ── Create / Edit Feed Modal ────────────────────────── */}
      <Dialog open={modalOpen} onClose={closeModal}>
        <form onSubmit={handleSave}>
          <DialogTitle>
            {editingFeed ? `Edit Feed: ${editingFeed.name}` : "Create Feed"}
          </DialogTitle>

          <div className="space-y-4">
            {/* Name */}
            <Input
              label="Name"
              placeholder="e.g. Slack Standup Summary"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              required
            />

            {/* Platform */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                Platform
              </label>
              <select
                className="flex h-9 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-50 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                value={form.platform}
                onChange={(e) => {
                  const platform = e.target.value;
                  setForm((p) => ({
                    ...p,
                    platform,
                    delivery_type: PLATFORM_DELIVERY[platform] ?? "mcp",
                  }));
                }}
              >
                <option value="slack">Slack</option>
              </select>
            </div>

            {/* Direction */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                Direction
              </label>
              <div className="flex gap-3">
                {DIRECTION_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 text-sm text-gray-300"
                  >
                    <input
                      type="radio"
                      name="direction"
                      value={opt.value}
                      checked={form.direction === opt.value}
                      onChange={() =>
                        setForm((p) => ({ ...p, direction: opt.value }))
                      }
                      className="accent-blue-500"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Conditional: Channel name */}
            {form.delivery_type === "channel" && (
              <Input
                label="Channel Name"
                placeholder="#meeting-notes"
                value={form.channel_name ?? ""}
                onChange={(e) =>
                  setForm((p) => ({ ...p, channel_name: e.target.value }))
                }
              />
            )}

            {/* Conditional: MCP fields */}
            {form.delivery_type === "mcp" && (
              <>
                <Input
                  label="MCP Server URL"
                  placeholder="https://mcp.example.com/sse"
                  value={form.mcp_server_url ?? ""}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, mcp_server_url: e.target.value }))
                  }
                />
                <Input
                  label="Auth Token"
                  type="password"
                  placeholder="Bearer token for the MCP server"
                  value={form.mcp_auth_token ?? ""}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, mcp_auth_token: e.target.value }))
                  }
                />
              </>
            )}

            {/* Data types */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                Data Types
              </label>
              <div className="flex flex-wrap gap-3">
                {DATA_TYPE_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 text-sm text-gray-300"
                  >
                    <input
                      type="checkbox"
                      checked={form.data_types.includes(opt.value)}
                      onChange={() => toggleDataType(opt.value)}
                      className="accent-blue-500"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Context types */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                Context Types (inbound)
              </label>
              <div className="flex flex-wrap gap-3">
                {CONTEXT_TYPE_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 text-sm text-gray-300"
                  >
                    <input
                      type="checkbox"
                      checked={(form.context_types ?? []).includes(opt.value)}
                      onChange={() => toggleContextType(opt.value)}
                      className="accent-blue-500"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Trigger */}
            <div className="space-y-1.5">
              <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                Trigger
              </label>
              <div className="flex gap-3">
                {TRIGGER_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 text-sm text-gray-300"
                  >
                    <input
                      type="radio"
                      name="trigger"
                      value={opt.value}
                      checked={form.trigger === opt.value}
                      onChange={() =>
                        setForm((p) => ({ ...p, trigger: opt.value }))
                      }
                      className="accent-blue-500"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Meeting tag filter */}
            <Input
              label="Meeting Tag Filter (optional)"
              placeholder="e.g. standup, sprint-review"
              value={form.meeting_tag ?? ""}
              onChange={(e) =>
                setForm((p) => ({ ...p, meeting_tag: e.target.value }))
              }
            />

            {saveError && (
              <div className="rounded-lg border border-red-900/60 bg-red-950/50 px-3 py-2 text-sm text-red-400">
                {saveError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeModal}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving || !form.name}>
              {isSaving
                ? "Saving..."
                : editingFeed
                  ? "Update Feed"
                  : "Create Feed"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="mr-2 h-4 w-4 animate-spin text-gray-500"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
