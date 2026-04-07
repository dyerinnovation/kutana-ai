import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { Feed, FeedCreate, Integration as IntegrationType, SlackChannel } from "@/types";
import { listFeeds, createFeed, updateFeed, toggleFeed, triggerFeed } from "@/api/feeds";
import { listIntegrations, connectSlack, listSlackChannels } from "@/api/integrations";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";
import { useAuth } from "@/hooks/useAuth";
import { FEED_LIMIT, upgradeTargetFor } from "@/lib/planLimits";
import { UpgradeBadge } from "@/components/UpgradeBadge";

/* ── Platform Icons ─────────────────────────────────────── */

function SlackIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="18" height="18" rx="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <text x="12" y="16.5" textAnchor="middle" fill="currentColor" fontSize="13" fontWeight="bold" fontFamily="sans-serif">#</text>
    </svg>
  );
}

function DiscordIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M19.27 5.33C17.94 4.71 16.5 4.26 15 4a.09.09 0 0 0-.07.03c-.18.33-.39.76-.53 1.09a16.09 16.09 0 0 0-4.8 0c-.14-.34-.36-.76-.54-1.09c-.01-.02-.04-.03-.07-.03c-1.5.26-2.93.71-4.27 1.33c-.01 0-.02.01-.03.02c-2.72 4.07-3.47 8.03-3.1 11.95c0 .02.01.04.03.05c1.8 1.32 3.53 2.12 5.24 2.65c.03.01.06 0 .07-.02c.4-.55.76-1.13 1.07-1.74c.02-.04 0-.08-.04-.09c-.57-.22-1.11-.48-1.64-.78c-.04-.02-.04-.08-.01-.11c.11-.08.22-.17.33-.25c.02-.02.05-.02.07-.01c3.44 1.57 7.15 1.57 10.55 0c.02-.01.05-.01.07.01c.11.09.22.17.33.26c.04.03.04.09-.01.11c-.52.31-1.07.56-1.64.78c-.04.01-.05.06-.04.09c.32.61.68 1.19 1.07 1.74c.03.01.06.02.09.01c1.72-.53 3.45-1.33 5.25-2.65c.02-.01.03-.03.03-.05c.44-4.53-.73-8.46-3.1-11.95c-.01-.01-.02-.02-.04-.02zM8.52 14.91c-1.03 0-1.89-.95-1.89-2.12s.84-2.12 1.89-2.12c1.06 0 1.9.96 1.89 2.12c0 1.17-.84 2.12-1.89 2.12zm6.97 0c-1.03 0-1.89-.95-1.89-2.12s.84-2.12 1.89-2.12c1.06 0 1.9.96 1.89 2.12c0 1.17-.83 2.12-1.89 2.12z" />
    </svg>
  );
}

function DefaultPlatformIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" xmlns="http://www.w3.org/2000/svg">
      <path d="M14.5 2H15a2 2 0 0 1 2 2v1.5a2 2 0 0 1-2 2h-1.5a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
      <path d="M9.5 9.5H10a2 2 0 0 1 2 2V13a2 2 0 0 1-2 2H9.5a2 2 0 0 1-2-2v-1.5a2 2 0 0 1 2-2z" />
      <path d="M14.5 16.5H15a2 2 0 0 1 2 2V20a2 2 0 0 1-2 2h-1.5a2 2 0 0 1-2-2v-1.5a2 2 0 0 1 2-2z" />
      <path d="M15 5.5h3.5a2 2 0 0 1 2 2V11" />
      <path d="M9.5 11.5H6a2 2 0 0 0-2 2V17" />
      <path d="M13 13v1.5a2 2 0 0 1 2 2" />
    </svg>
  );
}

function PlatformIcon({ platform, className = "h-4 w-4" }: { platform: string; className?: string }) {
  switch (platform) {
    case "slack":
      return <SlackIcon className={className} />;
    case "discord":
      return <DiscordIcon className={className} />;
    default:
      return <DefaultPlatformIcon className={className} />;
  }
}

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

interface PlatformCatalogEntry {
  id: string;
  name: string;
  description: string;
  status: "available" | "coming_soon" | "planned";
  platform: string;
}

const INTEGRATIONS: PlatformCatalogEntry[] = [
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
    status: "coming_soon",
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
  slack: "channel",
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
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const feedLimit = user
    ? FEED_LIMIT[user.plan_tier as keyof typeof FEED_LIMIT]
    : 0;
  const feedsBlocked = feedLimit === 0;

  // Feeds state
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [feedsLoading, setFeedsLoading] = useState(true);
  const [feedsError, setFeedsError] = useState<string | null>(null);

  // Integrations state (OAuth connections)
  const [integrations, setIntegrations] = useState<IntegrationType[]>([]);
  const [slackChannels, setSlackChannels] = useState<SlackChannel[]>([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const [slackConnected, setSlackConnected] = useState(false);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingFeed, setEditingFeed] = useState<Feed | null>(null);
  const [form, setForm] = useState<FeedCreate>({ ...EMPTY_FORM });
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const slackIntegration = integrations.find(
    (i) => i.platform === "slack" && i.status === "active",
  );

  useEffect(() => {
    loadFeeds();
    loadIntegrations();
  }, []);

  // Detect OAuth callback redirect
  useEffect(() => {
    if (searchParams.get("slack") === "connected") {
      setSlackConnected(true);
      setSearchParams({}, { replace: true });
      loadIntegrations();
      setTimeout(() => setSlackConnected(false), 5_000);
    }
  }, [searchParams, setSearchParams]);

  async function loadIntegrations() {
    try {
      const data = await listIntegrations();
      setIntegrations(data);
      const hasSlack = data.some((i) => i.platform === "slack" && i.status === "active");
      if (hasSlack) {
        try {
          const channels = await listSlackChannels();
          setSlackChannels(channels);
        } catch {
          setSlackChannels([]);
        }
      }
    } catch {
      setIntegrations([]);
    }
  }

  async function handleConnectSlack() {
    setIsConnecting(true);
    try {
      const { authorize_url } = await connectSlack();
      window.location.href = authorize_url;
    } catch (err) {
      setFeedsError(err instanceof Error ? err.message : "Failed to connect Slack");
      setIsConnecting(false);
    }
  }

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
        integration_id: form.platform === "slack" && slackIntegration ? slackIntegration.id : undefined,
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
          <Link
            to="/docs/feeds"
            className="mt-1 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            Learn more about Feeds
            <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M5.22 14.78a.75.75 0 0 1 0-1.06l7.22-7.22H8.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V7.06l-7.22 7.22a.75.75 0 0 1-1.06 0z" clipRule="evenodd" />
            </svg>
          </Link>
        </div>

        {feedsLoading && (
          <div className="flex items-center justify-center py-12 text-sm text-gray-500">
            <SpinnerIcon />
            Loading feeds...
          </div>
        )}

        {slackConnected && (
          <div className="rounded-lg border border-green-500/30 bg-green-600/10 px-4 py-3 text-sm text-green-400">
            Slack connected successfully! You can now create Slack feeds.
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
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600/15 text-blue-400">
                        <PlatformIcon platform={feed.platform} className="h-4 w-4" />
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
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-gray-50">
              Available Integrations
            </h2>
            <p className="mt-0.5 text-sm text-gray-400">
              Connect Kutana to your favorite platforms
            </p>
          </div>
          {feedsBlocked && (
            <UpgradeBadge requiredTier={upgradeTargetFor("feeds")} />
          )}
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
                  disabled={
                    integration.status !== "available" || feedsBlocked
                  }
                >
                  {feedsBlocked && integration.status === "available"
                    ? "Upgrade to unlock"
                    : integration.status === "available"
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
            {editingFeed ? (
              `Edit Feed: ${editingFeed.name}`
            ) : (
              <span className="inline-flex items-center gap-2">
                <PlatformIcon platform={form.platform} className="h-5 w-5 text-blue-400" />
                Create {INTEGRATIONS.find((i) => i.platform === form.platform)?.name ?? form.platform} Feed
              </span>
            )}
          </DialogTitle>

          <div className="space-y-4">
            {/* Platform selection cards (create mode only) */}
            {!editingFeed && (
              <div className="space-y-1.5">
                <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                  Platform
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {INTEGRATIONS.filter((i) => i.status === "available" || i.status === "coming_soon").map((integration) => {
                    const isSelected = form.platform === integration.platform;
                    const isDisabled = integration.status !== "available";
                    return (
                      <button
                        key={integration.id}
                        type="button"
                        disabled={isDisabled}
                        onClick={() =>
                          setForm((p) => ({
                            ...p,
                            platform: integration.platform,
                            delivery_type: PLATFORM_DELIVERY[integration.platform] ?? "mcp",
                          }))
                        }
                        className={`relative flex items-center gap-3 rounded-lg border px-3 py-3 text-left text-sm transition-all ${
                          isSelected
                            ? "border-blue-500 bg-blue-600/10 text-gray-50"
                            : isDisabled
                              ? "cursor-not-allowed border-gray-800 bg-gray-900/50 text-gray-500"
                              : "border-gray-700 bg-gray-900 text-gray-300 hover:border-gray-600 hover:bg-gray-800"
                        }`}
                      >
                        <PlatformIcon platform={integration.platform} className="h-5 w-5 flex-shrink-0" />
                        <span className="font-medium">{integration.name}</span>
                        {isDisabled && (
                          <span className="ml-auto inline-flex items-center rounded-md bg-yellow-600/20 px-1.5 py-0.5 text-[10px] font-medium text-yellow-400 border border-yellow-500/30">
                            Coming Soon
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Name */}
            <Input
              label="Name"
              placeholder="e.g. Slack Standup Summary"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              required
            />

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

            {/* Conditional: Slack OAuth connection */}
            {form.platform === "slack" && (
              <div className="space-y-1.5">
                <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                  Slack Connection
                </label>
                {slackIntegration ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-600/10 px-3 py-2 text-sm">
                      <svg className="h-4 w-4 text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
                      </svg>
                      <span className="text-green-400">
                        Connected to {slackIntegration.external_team_name ?? "Slack"}
                      </span>
                    </div>
                    {slackChannels.length > 0 && (
                      <div className="space-y-1.5">
                        <label className="block text-xs font-medium text-gray-400">Channel</label>
                        <select
                          className="flex h-10 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-50 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          value={form.channel_name ?? ""}
                          onChange={(e) => setForm((p) => ({ ...p, channel_name: e.target.value }))}
                        >
                          <option value="">Select a channel</option>
                          {slackChannels.map((ch) => (
                            <option key={ch.id} value={ch.name}>
                              #{ch.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-700 bg-gray-900/50 px-4 py-6">
                    <p className="text-sm text-gray-400">
                      Connect your Slack workspace to create feeds
                    </p>
                    <Button
                      type="button"
                      onClick={handleConnectSlack}
                      disabled={isConnecting}
                    >
                      <SlackIcon className="h-4 w-4" />
                      {isConnecting ? "Connecting..." : "Connect Slack"}
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Conditional: Channel name (non-Slack channel feeds) */}
            {form.delivery_type === "channel" && form.platform !== "slack" && (
              <Input
                label="Channel Name"
                placeholder="#meeting-notes"
                value={form.channel_name ?? ""}
                onChange={(e) =>
                  setForm((p) => ({ ...p, channel_name: e.target.value }))
                }
              />
            )}

            {/* Conditional: MCP fields (non-Slack MCP feeds) */}
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
