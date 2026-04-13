import { useEffect, useState, type FormEvent } from "react";
import type { AgentTemplate } from "@/types";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";
import { useAuth } from "@/hooks/useAuth";
import { meetsTier } from "@/lib/planLimits";

export interface TemplateOverrideValue {
  system_prompt_override: string | null;
  sop_id: string | null;
}

interface TemplateOverrideDialogProps {
  /** The template being customized, or null to close the dialog. */
  template: AgentTemplate | null;
  /** Existing override to seed the form with when opening. */
  initial?: TemplateOverrideValue | null;
  /** Called when the user dismisses without saving. */
  onClose: () => void;
  /** Called when the user saves — parent persists via setSelectedAgents. */
  onSave: (value: TemplateOverrideValue) => void;
}

/** Combines SOP content and custom instructions into a system_prompt_override. */
function buildSystemPromptOverride(
  sopContent: string,
  customInstructions: string,
): string | null {
  const parts: string[] = [];
  if (sopContent.trim()) {
    parts.push(`## Organization SOP\n\n${sopContent.trim()}`);
  }
  if (customInstructions.trim()) {
    parts.push(`## Custom Instructions\n\n${customInstructions.trim()}`);
  }
  return parts.length > 0 ? parts.join("\n\n---\n\n") : null;
}

/**
 * Customization dialog used by the meeting detail checkbox panel.
 *
 * Unlike ActivateTemplateDialog, this component does not pick a meeting
 * and does not call the activation API — the parent owns selection state
 * and persists via PUT /meetings/{id}/selected-agents.
 */
export function TemplateOverrideDialog({
  template,
  initial,
  onClose,
  onSave,
}: TemplateOverrideDialogProps) {
  const { user } = useAuth();
  const isBusiness = meetsTier(user, "business");

  const [sopContent, setSopContent] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");

  useEffect(() => {
    if (!template) return;
    setSopContent("");
    setCustomInstructions("");
  }, [template, initial]);

  function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!template) return;
    const systemPromptOverride = isBusiness
      ? buildSystemPromptOverride(sopContent, customInstructions)
      : null;
    onSave({
      system_prompt_override: systemPromptOverride,
      sop_id: initial?.sop_id ?? null,
    });
    onClose();
  }

  return (
    <Dialog open={template !== null} onClose={onClose}>
      <form onSubmit={handleSave} data-testid="template-override-dialog">
        <DialogTitle>Customize: {template?.name}</DialogTitle>
        <div className="space-y-4">
          {isBusiness ? (
            <div className="rounded-lg border border-purple-800/40 bg-purple-950/20 p-4 space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-purple-300">
                  Business Configuration
                </span>
                <span className="inline-flex items-center rounded-full bg-purple-600/20 border border-purple-500/30 px-1.5 py-0 text-[10px] font-medium text-purple-400">
                  Business+
                </span>
              </div>

              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-300">
                  Organization SOP
                  <span className="ml-1.5 text-xs font-normal text-gray-500">
                    optional
                  </span>
                </label>
                <textarea
                  data-testid="template-override-sop"
                  className="h-28 w-full rounded-lg border border-purple-800/40 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500/40 focus:outline-none resize-none"
                  placeholder="Paste your organization's standard operating procedure here. The agent will follow these guidelines during the meeting."
                  value={sopContent}
                  onChange={(e) => setSopContent(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-300">
                  Custom Instructions
                  <span className="ml-1.5 text-xs font-normal text-gray-500">
                    optional
                  </span>
                </label>
                <textarea
                  data-testid="template-override-custom-instructions"
                  className="h-20 w-full rounded-lg border border-purple-800/40 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-purple-500 focus:ring-1 focus:ring-purple-500/40 focus:outline-none resize-none"
                  placeholder="Any additional instructions for this specific meeting (e.g. focus on budget items, flag risks)."
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400">
              No customization options available for this template on your plan.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" data-testid="template-override-save">
            Save
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
