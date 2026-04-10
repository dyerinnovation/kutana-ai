import { useEffect, useState, type FormEvent } from "react";
import type { AgentTemplate, HostedSession, Meeting } from "@/types";
import { activateTemplate } from "@/api/agentTemplates";
import { listMeetings } from "@/api/meetings";
import { PROMPT_PRESETS } from "@/lib/promptPresets";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";
import { useAuth } from "@/hooks/useAuth";
import { meetsTier } from "@/lib/planLimits";

interface ActivateTemplateDialogProps {
  /** The template being activated, or null to close the dialog. */
  template: AgentTemplate | null;
  /** Called when the user dismisses the dialog. */
  onClose: () => void;
  /** Called after successful activation. */
  onActivated?: (session: HostedSession) => void;
}

/** Combines SOP content and custom instructions into a system_prompt_override. */
function buildSystemPromptOverride(
  sopContent: string,
  customInstructions: string,
  promptOverride: string,
): string | undefined {
  const parts: string[] = [];
  if (sopContent.trim()) {
    parts.push(`## Organization SOP\n\n${sopContent.trim()}`);
  }
  if (customInstructions.trim()) {
    parts.push(`## Custom Instructions\n\n${customInstructions.trim()}`);
  }
  if (promptOverride.trim()) {
    parts.push(promptOverride.trim());
  }
  return parts.length > 0 ? parts.join("\n\n---\n\n") : undefined;
}

export function ActivateTemplateDialog({
  template,
  onClose,
  onActivated,
}: ActivateTemplateDialogProps) {
  const { user } = useAuth();
  const isBusiness = meetsTier(user, "business");

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedMeetingId, setSelectedMeetingId] = useState("");
  const [isActivating, setIsActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Business+ fields
  const [sopContent, setSopContent] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");

  // Prompt customization (all tiers)
  const [showPromptCustomize, setShowPromptCustomize] = useState(false);
  const [promptOverride, setPromptOverride] = useState("");

  // Load meetings when dialog opens
  useEffect(() => {
    if (!template) return;
    setSelectedMeetingId("");
    setError(null);
    setShowPromptCustomize(false);
    setPromptOverride("");
    setSopContent("");
    setCustomInstructions("");
    listMeetings()
      .then((res) =>
        setMeetings(
          res.items.filter(
            (m) => m.status === "scheduled" || m.status === "active",
          ),
        ),
      )
      .catch(() => setMeetings([]));
  }, [template]);

  async function handleActivate(e: FormEvent) {
    e.preventDefault();
    if (!template || !selectedMeetingId) return;

    setIsActivating(true);
    setError(null);
    try {
      const systemPromptOverride = isBusiness
        ? buildSystemPromptOverride(sopContent, customInstructions, promptOverride)
        : promptOverride || undefined;

      const session = await activateTemplate(
        template.id,
        selectedMeetingId,
        systemPromptOverride,
      );
      onActivated?.(session);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to activate template",
      );
    } finally {
      setIsActivating(false);
    }
  }

  return (
    <Dialog open={template !== null} onClose={onClose}>
      <form onSubmit={handleActivate}>
        <DialogTitle>Activate: {template?.name}</DialogTitle>
        <div className="space-y-4">
          {/* Meeting selector */}
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

          {/* Business+ configuration */}
          {isBusiness && (
            <div className="rounded-lg border border-purple-800/40 bg-purple-950/20 p-4 space-y-4">
              <div className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 text-purple-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"
                  />
                </svg>
                <span className="text-sm font-medium text-purple-300">
                  Business Configuration
                </span>
                <span className="inline-flex items-center rounded-full bg-purple-600/20 border border-purple-500/30 px-1.5 py-0 text-[10px] font-medium text-purple-400">
                  Business+
                </span>
              </div>

              {/* Organization SOP */}
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-300">
                  Organization SOP
                  <span className="ml-1.5 text-xs font-normal text-gray-500">
                    optional
                  </span>
                </label>
                <textarea
                  className="h-28 w-full rounded-lg border border-purple-800/40 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500/40 focus:outline-none resize-none"
                  placeholder="Paste your organization's standard operating procedure here. The agent will follow these guidelines during the meeting."
                  value={sopContent}
                  onChange={(e) => setSopContent(e.target.value)}
                />
                <p className="text-xs text-gray-500">
                  The agent will be instructed to follow this SOP throughout the meeting.
                </p>
              </div>

              {/* Custom Instructions */}
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-300">
                  Custom Instructions
                  <span className="ml-1.5 text-xs font-normal text-gray-500">
                    optional
                  </span>
                </label>
                <textarea
                  className="h-20 w-full rounded-lg border border-purple-800/40 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500/40 focus:outline-none resize-none"
                  placeholder="Any additional instructions for this specific meeting (e.g. focus on budget items, flag risks)."
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Prompt customization — all tiers */}
          <div>
            <button
              type="button"
              onClick={() => setShowPromptCustomize(!showPromptCustomize)}
              className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
              <svg
                className={`h-3.5 w-3.5 transition-transform ${showPromptCustomize ? "rotate-90" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8.25 4.5l7.5 7.5-7.5 7.5"
                />
              </svg>
              Customize Prompt (optional)
            </button>

            {showPromptCustomize && (
              <div className="mt-3 space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  {PROMPT_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setPromptOverride(preset.prompt)}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                        promptOverride === preset.prompt
                          ? "bg-blue-600 text-white"
                          : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
                <textarea
                  className="h-32 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 focus:outline-none resize-none"
                  placeholder={
                    isBusiness
                      ? "Override the full system prompt (combined with SOP and custom instructions above)."
                      : "Enter a custom system prompt..."
                  }
                  value={promptOverride}
                  onChange={(e) => setPromptOverride(e.target.value)}
                />
                <p className="text-xs text-gray-500">
                  {isBusiness
                    ? "Combined with Business configuration above when provided."
                    : "Leave blank to use the template\u2019s default prompt."}
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="rounded-lg border border-red-800 bg-red-950/50 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
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
  );
}
