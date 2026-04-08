import type { TurnQueueEntry, Participant } from "@/types";

interface SpeakerQueuePanelProps {
  activeSpeaker: { id: string; name: string } | null;
  queue: TurnQueueEntry[];
  participants: Participant[];
  currentUserId: string | undefined;
  isMyTurn: boolean;
  onFinishedSpeaking: () => void;
}

export function SpeakerQueuePanel({
  activeSpeaker,
  queue,
  participants,
  currentUserId,
  isMyTurn,
  onFinishedSpeaking,
}: SpeakerQueuePanelProps) {
  const resolveName = (participantId: string): string => {
    if (participantId === currentUserId) return "You";
    const p = participants.find((x) => x.id === participantId);
    return p?.name ?? "Unknown";
  };

  const hasContent = activeSpeaker || queue.length > 0;
  if (!hasContent) return null;

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3 space-y-3">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
        Speaker Queue
      </h3>

      {/* Active speaker */}
      {activeSpeaker && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-700/50 bg-emerald-950/40 px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-xs text-gray-400">Speaking now</span>
            <p className="text-sm font-semibold text-emerald-300 truncate">
              {activeSpeaker.id === currentUserId ? "You" : activeSpeaker.name}
            </p>
          </div>
          {isMyTurn && (
            <button
              onClick={onFinishedSpeaking}
              className="rounded-md bg-emerald-700 px-2.5 py-1 text-xs font-medium text-emerald-100 hover:bg-emerald-600 transition-colors flex-shrink-0"
            >
              Done
            </button>
          )}
        </div>
      )}

      {/* Queued speakers */}
      {queue.length > 0 && (
        <div className="space-y-1.5">
          {queue.map((entry, i) => {
            const name = entry.name || resolveName(entry.participant_id);
            const isMe = entry.participant_id === currentUserId;
            return (
              <div
                key={entry.hand_raise_id}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${
                  isMe
                    ? "border border-amber-600/40 bg-amber-950/30"
                    : "border border-gray-800 bg-gray-900/30"
                }`}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-900/60 text-amber-400 text-[10px] font-bold flex-shrink-0">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <span className={`font-medium ${isMe ? "text-amber-300" : "text-gray-300"}`}>
                    {name}
                    {isMe && " (you)"}
                  </span>
                  {entry.topic && (
                    <p className="text-gray-500 truncate mt-0.5">{entry.topic}</p>
                  )}
                </div>
                {entry.priority === "urgent" && (
                  <span className="rounded-full bg-red-900/50 border border-red-700/40 px-1.5 py-0 text-[10px] font-medium text-red-300 flex-shrink-0">
                    Urgent
                  </span>
                )}
                <HandIconSmall />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function HandIconSmall() {
  return (
    <svg
      className="h-3.5 w-3.5 text-amber-500 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.05 4.575a1.575 1.575 0 1 0-3.15 0v3m3.15-3v-1.5a1.575 1.575 0 0 1 3.15 0v1.5m0 0v-1.5a1.575 1.575 0 0 1 3.15 0v1.5m0 0a1.575 1.575 0 0 1 3.15 0V12a4.5 4.5 0 0 1-4.5 4.5 1.5 1.5 0 0 1-1.5-1.5V12H6.9a1.575 1.575 0 0 0-.45 3.083L8.25 18v.75a2.25 2.25 0 0 0 2.25 2.25h6a2.25 2.25 0 0 0 2.25-2.25v-.75l1.8-2.917A1.575 1.575 0 0 0 20.1 12V7.575a1.575 1.575 0 0 0-3.15 0"
      />
    </svg>
  );
}
