import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { AgentTemplate, Meeting, SelectedAgent } from "@/types";
import {
  createMeeting,
  deleteMeeting,
  endMeeting,
  getSelectedAgents,
  listMeetings,
  setSelectedAgents,
  startMeeting,
} from "@/api/meetings";
import { listTemplates } from "@/api/agentTemplates";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";
import {
  TemplateOverrideDialog,
  type TemplateOverrideValue,
} from "@/components/TemplateOverrideDialog";
import { showToast } from "@/components/Toast";
import { useAuth } from "@/hooks/useAuth";
import { canActivateTemplate, meetsTier } from "@/lib/planLimits";

const SELECTION_DEBOUNCE_MS = 300;

/**
 * Upserts a selection for `templateId` into an existing selections list.
 * Adding a selection with no override values still persists the template_id.
 */
function mergeSelection(
  selections: SelectedAgent[],
  templateId: string,
  override: Partial<TemplateOverrideValue>,
): SelectedAgent[] {
  const existing = selections.find((s) => s.template_id === templateId);
  const next: SelectedAgent = {
    template_id: templateId,
    system_prompt_override:
      override.system_prompt_override ?? existing?.system_prompt_override ?? null,
    sop_id: override.sop_id ?? existing?.sop_id ?? null,
  };
  if (existing) {
    return selections.map((s) => (s.template_id === templateId ? next : s));
  }
  return [...selections, next];
}

export function MeetingsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create meeting state
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Per-meeting agent selection state
  const [selectionsByMeeting, setSelectionsByMeeting] = useState<
    Record<string, SelectedAgent[]>
  >({});
  const [expandedMeetingId, setExpandedMeetingId] = useState<string | null>(null);
  const [overrideTarget, setOverrideTarget] = useState<{
    meetingId: string;
    template: AgentTemplate;
  } | null>(null);

  // Debounce timers for PUT /selected-agents, keyed by meeting id.
  const debounceTimersRef = useRef<Record<string, number>>({});

  // Delete confirmation dialog target.
  const [deleteTarget, setDeleteTarget] = useState<Meeting | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    loadMeetings();
    listTemplates()
      .then((items) => setTemplates(items))
      .catch(() => setTemplates([]));
  }, []);

  // Auto-open create dialog when navigated with ?create=true
  useEffect(() => {
    if (searchParams.get("create") === "true") {
      setShowCreate(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Cancel any pending debounced saves on unmount.
  useEffect(() => {
    const timers = debounceTimersRef.current;
    return () => {
      Object.values(timers).forEach((handle) => window.clearTimeout(handle));
    };
  }, []);

  async function loadMeetings() {
    try {
      const res = await listMeetings();
      setMeetings(res.items);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load meetings"
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setIsCreating(true);
    setError(null);

    try {
      await createMeeting({
        title,
        platform: "kutana",
        scheduled_at: new Date(scheduledAt).toISOString(),
      });
      setShowCreate(false);
      setTitle("");
      setScheduledAt("");
      await loadMeetings();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create meeting"
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleStart(meetingId: string) {
    setError(null);
    try {
      await startMeeting(meetingId);
      // The meeting room renders per-agent warming state — no blocking
      // loading state on this page. Navigate straight in.
      navigate(`/meetings/${meetingId}/room`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start meeting"
      );
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deleteMeeting(deleteTarget.id);
      setMeetings((prev) => prev.filter((m) => m.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : "Failed to delete meeting",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleEnd(meetingId: string) {
    setError(null);
    try {
      await endMeeting(meetingId);
      await loadMeetings();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to end meeting"
      );
    }
  }

  /** Lazily load the current server-side selection for a meeting. */
  const loadSelectionsForMeeting = useCallback(
    async (meetingId: string) => {
      if (selectionsByMeeting[meetingId]) return;
      try {
        const items = await getSelectedAgents(meetingId);
        setSelectionsByMeeting((prev) => ({ ...prev, [meetingId]: items }));
      } catch {
        setSelectionsByMeeting((prev) => ({ ...prev, [meetingId]: [] }));
      }
    },
    [selectionsByMeeting],
  );

  /** Debounced PUT /selected-agents for a single meeting. */
  const scheduleSelectionSave = useCallback(
    (meetingId: string, selections: SelectedAgent[]) => {
      const timers = debounceTimersRef.current;
      if (timers[meetingId]) {
        window.clearTimeout(timers[meetingId]);
      }
      timers[meetingId] = window.setTimeout(async () => {
        try {
          await setSelectedAgents(meetingId, selections);
        } catch (err) {
          showToast(
            err instanceof Error
              ? err.message
              : "Failed to save agent selection",
          );
        } finally {
          delete timers[meetingId];
        }
      }, SELECTION_DEBOUNCE_MS);
    },
    [],
  );

  function toggleExpanded(meetingId: string) {
    if (expandedMeetingId === meetingId) {
      setExpandedMeetingId(null);
      return;
    }
    setExpandedMeetingId(meetingId);
    void loadSelectionsForMeeting(meetingId);
  }

  function handleToggleTemplate(meetingId: string, template: AgentTemplate) {
    const current = selectionsByMeeting[meetingId] ?? [];
    const isSelected = current.some((s) => s.template_id === template.id);
    const next = isSelected
      ? current.filter((s) => s.template_id !== template.id)
      : mergeSelection(current, template.id, {});
    setSelectionsByMeeting((prev) => ({ ...prev, [meetingId]: next }));
    scheduleSelectionSave(meetingId, next);
  }

  function handleSaveOverride(
    meetingId: string,
    template: AgentTemplate,
    override: TemplateOverrideValue,
  ) {
    const current = selectionsByMeeting[meetingId] ?? [];
    // Saving an override implicitly selects the template.
    const next = mergeSelection(current, template.id, override);
    setSelectionsByMeeting((prev) => ({ ...prev, [meetingId]: next }));
    scheduleSelectionSave(meetingId, next);
  }

  function formatDateTime(dateStr: string): string {
    return new Date(dateStr).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  const isBusiness = meetsTier(user, "business");
  const availableTemplates = templates.filter((t) =>
    canActivateTemplate(user, t.tier),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-50">Meetings</h1>
          <p className="text-sm text-gray-400 mt-1">
            Schedule and manage your meetings
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Create Meeting</Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          Loading meetings...
        </div>
      )}

      {!isLoading && meetings.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-400 mb-4">No meetings scheduled yet.</p>
            <Button onClick={() => setShowCreate(true)}>
              Schedule your first meeting
            </Button>
          </CardContent>
        </Card>
      )}

      {meetings.length > 0 && (
        <div className="space-y-3">
          {meetings.map((meeting) => {
            const isScheduled = meeting.status === "scheduled";
            const isExpanded = expandedMeetingId === meeting.id;
            const selections = selectionsByMeeting[meeting.id] ?? [];
            const selectedCount = selections.length;
            return (
              <Card key={meeting.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>{meeting.title}</CardTitle>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                        meeting.status === "active"
                          ? "bg-green-600/20 text-green-400 border border-green-500/30"
                          : meeting.status === "completed"
                            ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                            : "bg-gray-600/20 text-gray-400 border border-gray-500/30"
                      }`}
                    >
                      {meeting.status.charAt(0).toUpperCase() + meeting.status.slice(1)}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex gap-6 text-sm text-gray-400">
                      <div>
                        <span className="text-gray-500">Scheduled: </span>
                        {formatDateTime(meeting.scheduled_at)}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {isScheduled && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => toggleExpanded(meeting.id)}
                            data-testid={`meeting-${meeting.id}-choose-agents`}
                          >
                            {isExpanded ? "Hide agents" : "Choose agents"}
                            {selectedCount > 0 && ` (${selectedCount})`}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleStart(meeting.id)}
                            data-testid={`meeting-${meeting.id}-start`}
                          >
                            Start
                          </Button>
                        </>
                      )}
                      {meeting.status === "active" && (
                        <>
                          <Button
                            size="sm"
                            onClick={() =>
                              navigate(`/meetings/${meeting.id}/room`)
                            }
                          >
                            Join Room
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleEnd(meeting.id)}
                          >
                            End
                          </Button>
                        </>
                      )}
                      {meeting.status !== "active" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setDeleteTarget(meeting)}
                          data-testid={`meeting-${meeting.id}-delete`}
                          aria-label="Delete meeting"
                          title="Delete meeting"
                        >
                          Delete
                        </Button>
                      )}
                    </div>
                  </div>

                  {isScheduled && isExpanded && (
                    <div className="mt-4 rounded-lg border border-gray-800 bg-gray-950/50 p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-gray-200">
                          Choose agents to join this meeting
                        </h3>
                        <span className="text-xs text-gray-500">
                          {selectedCount} selected
                        </span>
                      </div>

                      {availableTemplates.length === 0 ? (
                        <p className="text-sm text-gray-500">
                          No agent templates available on your plan.
                        </p>
                      ) : (
                        <ul className="space-y-2">
                          {availableTemplates.map((template) => {
                            const current = selections.find(
                              (s) => s.template_id === template.id,
                            );
                            const checked = Boolean(current);
                            const hasOverride = Boolean(
                              current?.system_prompt_override || current?.sop_id,
                            );
                            return (
                              <li
                                key={template.id}
                                className="flex items-start gap-3 rounded-md border border-gray-800 bg-gray-900/40 px-3 py-2"
                              >
                                <input
                                  id={`tpl-${meeting.id}-${template.id}`}
                                  data-testid={`meeting-${meeting.id}-template-${template.id}-checkbox`}
                                  type="checkbox"
                                  className="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-800 text-emerald-500 focus:ring-emerald-500"
                                  checked={checked}
                                  onChange={() =>
                                    handleToggleTemplate(meeting.id, template)
                                  }
                                />
                                <label
                                  htmlFor={`tpl-${meeting.id}-${template.id}`}
                                  className="flex-1 cursor-pointer"
                                >
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-gray-100">
                                      {template.name}
                                    </span>
                                    {hasOverride && (
                                      <span className="inline-flex items-center rounded-full bg-purple-600/20 border border-purple-500/30 px-1.5 py-0 text-[10px] font-medium text-purple-400">
                                        Customized
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                                    {template.description}
                                  </p>
                                </label>
                                {isBusiness && (
                                  <button
                                    type="button"
                                    data-testid={`meeting-${meeting.id}-template-${template.id}-gear`}
                                    className="text-gray-500 hover:text-gray-200 transition-colors"
                                    title="Customize for this meeting"
                                    onClick={() =>
                                      setOverrideTarget({
                                        meetingId: meeting.id,
                                        template,
                                      })
                                    }
                                  >
                                    <GearIcon />
                                  </button>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Meeting Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)}>
        <form onSubmit={handleCreate}>
          <DialogTitle>Schedule Meeting</DialogTitle>
          <div className="space-y-4">
            <Input
              label="Title"
              placeholder="Weekly standup"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
            <Input
              label="Date & Time"
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-300">
                Description
              </label>
              <textarea
                className="h-20 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 focus:outline-none resize-none"
                placeholder="Meeting agenda or notes..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCreate(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isCreating}>
              {isCreating ? "Creating..." : "Create Meeting"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => !isDeleting && setDeleteTarget(null)}
      >
        <DialogTitle>Delete meeting?</DialogTitle>
        <p className="text-sm text-gray-300">
          This will permanently delete{" "}
          <span className="font-medium text-gray-100">
            {deleteTarget?.title || "this meeting"}
          </span>{" "}
          and all associated transcripts, tasks, and agent sessions. This
          cannot be undone.
        </p>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setDeleteTarget(null)}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={confirmDelete}
            disabled={isDeleting}
            data-testid="confirm-delete-meeting"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </Dialog>

      {/* Per-template override dialog */}
      <TemplateOverrideDialog
        template={overrideTarget?.template ?? null}
        initial={(() => {
          if (!overrideTarget) return null;
          const found = (selectionsByMeeting[overrideTarget.meetingId] ?? []).find(
            (s) => s.template_id === overrideTarget.template.id,
          );
          if (!found) return null;
          return {
            system_prompt_override: found.system_prompt_override ?? null,
            sop_id: found.sop_id ?? null,
          };
        })()}
        onClose={() => setOverrideTarget(null)}
        onSave={(value) => {
          if (!overrideTarget) return;
          handleSaveOverride(
            overrideTarget.meetingId,
            overrideTarget.template,
            value,
          );
        }}
      />
    </div>
  );
}

function GearIcon() {
  return (
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  );
}
