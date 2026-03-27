export const CAPABILITY_LABELS: Record<string, string> = {
  transcription: "Transcription",
  task_extraction: "Task Extraction",
  summarization: "Summarization",
  action_items: "Action Items",
  voice: "Voice",
};

export const CAPABILITY_TOOLTIPS: Record<string, string> = {
  transcription: "Real-time speech-to-text transcription of meeting audio",
  task_extraction: "Automatic detection and extraction of action items from conversation",
  summarization: "Periodic meeting summaries generated during and after meetings",
  action_items: "Track commitments and assignments as they are spoken",
  voice: "Text-to-speech output so the agent can speak in meetings",
};

export function formatCapability(cap: string): string {
  if (cap in CAPABILITY_LABELS) return CAPABILITY_LABELS[cap];
  return cap
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
