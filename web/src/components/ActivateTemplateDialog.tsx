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
  const [selectedSopId, setSelectedSopId] = useState("");

  // Prompt customization
  const [showPromptCustomize, setShowPromptCustomize] = useState(false);
  const [promptOverride, setPromptOverride] = useState("");

  // Load meetings when dialog opens
  useEffect(() => {
    if (!template) return;
    setSelectedMeetingId("");
    setError(null);
    setShowPromptCustomize(false);
    setPromptOverride("");
    setSelectedSopId("");
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
      const session = await activateTemplate(
        template.id,
        selectedMeetingId,
        promptOverride || undefined,
        selectedSopId || undefined,
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

          {/* SOP selector — Business+ only */}
          {isBusiness && (
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-300">
                Standard Operating Procedure
                <span className="ml-1.5 inline-flex items-center rounded-full bg-purple-600/20 text-purple-400 border border-purple-500/30 px-1.5 py-0 text-[10px] font-medium">
                  Business
                </span>
              </label>
              <select
                className="flex h-10 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-50 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={selectedSopId}
                onChange={(e) => setSelectedSopId(e.target.value)}
              >
                <option value="">None (use default prompt)</option>
              </select>
              <p className="text-xs text-gray-500">
                Attach an organization SOP to guide the agent&apos;s behavior.
              </p>
            </div>
          )}

          {/* Prompt customization */}
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
                  placeholder="Enter a custom system prompt..."
                  value={promptOverride}
                  onChange={(e) => setPromptOverride(e.target.value)}
                />
                <p className="text-xs text-gray-500">
                  Leave blank to use the template&apos;s default prompt.
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
