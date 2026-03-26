import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { getMeetingToken } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import type {
  TranscriptSegment,
  Participant,
  GatewayMessage,
} from "@/types";

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const HUMAN_WS_BASE = `${wsProto}//${window.location.host}/human/connect`;
const SAMPLE_RATE = 16000;

// Energy gate: drop audio frames where the RMS level is below this threshold.
// This prevents streaming pure silence / ambient noise to the STT backend,
// which is the primary cause of Whisper hallucinations ("Thank you." etc.).
// ~0.01 ≈ -40 dBFS — consistent with what major meeting platforms use.
const RMS_SILENCE_THRESHOLD = 0.01;

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

function getGridClasses(count: number): string {
  if (count === 1) return "grid-cols-1 max-w-lg mx-auto";
  if (count === 2) return "grid-cols-2";
  if (count <= 4) return "grid-cols-2";
  if (count <= 6) return "grid-cols-3";
  return "grid-cols-3 xl:grid-cols-4";
}

function getTileHeight(count: number): string {
  if (count === 1) return "h-full min-h-[400px]";
  if (count === 2) return "h-72";
  if (count <= 4) return "h-60";
  if (count <= 6) return "h-48";
  return "h-40";
}

function getAvatarSize(count: number): string {
  if (count <= 2) return "h-28 w-28 text-4xl";
  if (count <= 4) return "h-24 w-24 text-3xl";
  return "h-20 w-20 text-2xl";
}

export function MeetingRoomPage() {
  const { id: meetingId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll transcript panel
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "leave_meeting" }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    if (workletRef.current) {
      workletRef.current.disconnect();
      workletRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const handleWsMessage = useCallback((event: MessageEvent) => {
    let msg: GatewayMessage;
    try {
      msg = JSON.parse(event.data) as GatewayMessage;
    } catch {
      return;
    }

    switch (msg.type) {
      case "transcript": {
        const seg: TranscriptSegment = {
          speaker_id: msg.speaker_id ?? "unknown",
          text: msg.text,
          start_time: msg.start_time,
          end_time: msg.end_time,
          confidence: msg.confidence,
          is_final: msg.is_final,
        };
        setTranscripts((prev) => {
          // Replace non-final segment from same speaker, or append
          if (!seg.is_final) {
            const idx = prev.findIndex(
              (s) => s.speaker_id === seg.speaker_id && !s.is_final
            );
            if (idx !== -1) {
              const updated = [...prev];
              updated[idx] = seg;
              return updated;
            }
          }
          return [...prev, seg];
        });
        break;
      }
      case "participant_update":
        // Server sends one participant per update (join/leave notification)
        setParticipants((prev) => {
          if (msg.action === "joined") {
            const p: Participant = { id: msg.participant_id, name: msg.name, role: msg.role, is_muted: false };
            return prev.some((x) => x.id === p.id) ? prev : [...prev, p];
          } else {
            return prev.filter((x) => x.id !== msg.participant_id);
          }
        });
        break;
      case "joined":
        setStatus("connected");
        break;
      case "error":
        setError(msg.message);
        break;
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    if (!meetingId) return;

    let cancelled = false;

    async function connect() {
      console.log("[Meeting] connect() started, meetingId=", meetingId);
      try {
        // 1. Get gateway token
        const { token } = await getMeetingToken(meetingId!);
        console.log("[Meeting] got token, cancelled=", cancelled);
        if (cancelled) return;

        // 2. Open WebSocket — meeting_id in URL, no join_meeting message needed
        const wsUrl = `${HUMAN_WS_BASE}?token=${token}&meeting_id=${meetingId}`;
        console.log("[Meeting] opening WS:", wsUrl.split("?")[0]);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        // No onopen send needed: server auto-joins on connect and sends "joined"
        ws.onopen = () => { console.log("[WS] opened"); };

        ws.onmessage = (event) => {
          console.log("[WS] message:", event.data.slice(0, 200));
          handleWsMessage(event);
        };

        ws.onerror = (e) => {
          console.error("[WS] error event:", e);
          if (!cancelled) {
            setStatus("error");
            setError("WebSocket connection failed");
          }
        };

        ws.onclose = (e) => {
          console.log("[WS] closed: code=", e.code, "reason=", e.reason, "clean=", e.wasClean);
          if (!cancelled) setStatus("disconnected");
        };

        // 3. Start audio capture
        console.log("[Meeting] calling getUserMedia, mediaDevices=", !!navigator.mediaDevices);
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: SAMPLE_RATE,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
        console.log("[Meeting] getUserMedia succeeded, cancelled=", cancelled);
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;

        const audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
        audioContextRef.current = audioCtx;

        // Use ScriptProcessorNode as fallback (widely supported)
        const source = audioCtx.createMediaStreamSource(stream);
        const processor = audioCtx.createScriptProcessor(4096, 1, 1);

        processor.onaudioprocess = (e: AudioProcessingEvent) => {
          if (
            wsRef.current?.readyState !== WebSocket.OPEN ||
            isMutedRef.current
          )
            return;

          const input = e.inputBuffer.getChannelData(0);

          // Energy gate: skip silent frames to avoid sending ambient noise to
          // the STT backend (primary cause of Whisper hallucinations).
          let sumSq = 0;
          for (let i = 0; i < input.length; i++) sumSq += input[i] * input[i];
          const rms = Math.sqrt(sumSq / input.length);
          if (rms < RMS_SILENCE_THRESHOLD) return;
          // Convert Float32 [-1,1] to Int16
          const pcm16 = new Int16Array(input.length);
          for (let i = 0; i < input.length; i++) {
            const s = Math.max(-1, Math.min(1, input[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          // Base64 encode
          const bytes = new Uint8Array(pcm16.buffer);
          let binary = "";
          for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const b64 = btoa(binary);

          wsRef.current.send(
            JSON.stringify({
              type: "audio_data",
              data: b64,
              sample_rate: SAMPLE_RATE,
            })
          );
        };

        source.connect(processor);
        processor.connect(audioCtx.destination);
      } catch (err) {
        console.error("[Meeting] connect() error:", err);
        if (!cancelled) {
          setStatus("error");
          setError(
            err instanceof Error ? err.message : "Failed to connect"
          );
        }
      }
    }

    connect();

    return () => {
      console.log("[Meeting] effect cleanup, cancelled=", cancelled);
      cancelled = true;
      cleanup();
    };
  }, [meetingId, handleWsMessage, cleanup]);

  // Keep a ref for mute state so the audio callback can read it
  const isMutedRef = useRef(isMuted);
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  function handleLeave() {
    cleanup();
    navigate("/meetings");
  }

  const otherParticipants = participants.filter((p) => p.id !== user?.id);

  function toggleMute() {
    setIsMuted((prev) => {
      const next = !prev;
      // Also mute the actual media track
      if (streamRef.current) {
        streamRef.current.getAudioTracks().forEach((t) => {
          t.enabled = !next;
        });
      }
      return next;
    });
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-50">Meeting Room</h1>
          <p className="text-xs text-gray-500 font-mono mt-0.5">
            {meetingId}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Main content: participants (main) + transcript (sidebar) */}
      <div className="flex flex-col md:flex-row flex-1 gap-4 min-h-0">
        {/* Participants grid — main panel */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-gray-800 bg-gray-900/50 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">
            Participants ({participants.length + 1})
          </h2>
          <div className={`grid ${getGridClasses(otherParticipants.length + 1)} gap-4`}>
            {/* Current user card */}
            <div className={`relative flex flex-col items-center justify-center ${getTileHeight(otherParticipants.length + 1)} w-full rounded-xl border border-emerald-700/50 bg-gray-900/50 p-4`}>
              <div className="relative mb-3">
                <div className={`${getAvatarSize(otherParticipants.length + 1)} rounded-full bg-emerald-600 flex items-center justify-center font-semibold text-white`}>
                  {user?.name?.charAt(0).toUpperCase() ?? "?"}
                </div>
                {!isMuted && (
                  <div className={`absolute inset-0 ${getAvatarSize(otherParticipants.length + 1)} rounded-full border-2 border-green-400 animate-pulse`} />
                )}
              </div>
              <p className="text-lg font-medium text-gray-50 truncate max-w-full">
                {user?.name ?? "You"}
              </p>
              <p className="text-sm text-gray-400">You</p>
              {isMuted && (
                <div className="absolute top-3 right-3 text-red-400" title="Muted">
                  <MicOffIconSmall />
                </div>
              )}
            </div>

            {/* Other participants */}
            {otherParticipants.map((p) => (
                <div
                  key={p.id}
                  className={`relative flex flex-col items-center justify-center ${getTileHeight(otherParticipants.length + 1)} w-full rounded-xl border border-gray-800 bg-gray-900/50 p-4`}
                >
                  <div className="relative mb-3">
                    {p.avatar_url ? (
                      <img
                        src={p.avatar_url}
                        alt={p.name}
                        className={`${getAvatarSize(otherParticipants.length + 1)} rounded-full object-cover`}
                      />
                    ) : (
                      <div className={`${getAvatarSize(otherParticipants.length + 1)} rounded-full bg-gray-700 flex items-center justify-center font-semibold text-gray-300`}>
                        {p.name.charAt(0).toUpperCase()}
                      </div>
                    )}
                    {p.is_speaking && (
                      <div className={`absolute inset-0 ${getAvatarSize(otherParticipants.length + 1)} rounded-full border-2 border-green-400 animate-pulse`} />
                    )}
                  </div>
                  <p className="text-lg font-medium text-gray-200 truncate max-w-full">
                    {p.name}
                  </p>
                  <p className="text-sm text-gray-400">{p.role}</p>
                  {p.is_muted && (
                    <div className="absolute top-3 right-3 text-red-400" title="Muted">
                      <MicOffIconSmall />
                    </div>
                  )}
                </div>
              ))}
          </div>
        </div>

        {/* Transcript sidebar — right */}
        <div className="w-full md:w-80 md:flex-shrink-0 flex flex-col rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-800">
            <TranscriptIcon />
            <h2 className="text-xs font-semibold text-gray-300">Transcript</h2>
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
            {transcripts.length === 0 && status === "connected" && (
              <p className="text-xs text-gray-500 text-center py-6">
                Waiting for speech...
              </p>
            )}
            {transcripts.length === 0 && status === "connecting" && (
              <p className="text-xs text-gray-500 text-center py-6">
                Connecting to meeting...
              </p>
            )}
            {transcripts.map((seg, i) => (
              <div
                key={`${seg.speaker_id}-${seg.start_time}-${i}`}
                className={`text-xs leading-snug ${seg.is_final ? "text-gray-300" : "text-gray-500 italic"}`}
              >
                <span className="font-medium text-blue-400">
                  {seg.speaker_id}
                </span>
                <span className="text-gray-600 mx-1 text-[10px]">
                  {formatTimestamp(seg.start_time)}
                </span>
                <span>{seg.text}</span>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </div>
      </div>

      {/* Sticky bottom controls bar */}
      <div className="mt-4 flex items-center justify-center gap-4 border-t border-gray-800 pt-4">
        <Button
          variant={isMuted ? "destructive" : "outline"}
          onClick={toggleMute}
        >
          {isMuted ? (
            <>
              <MicOffIcon /> Unmute
            </>
          ) : (
            <>
              <MicIcon /> Mute
            </>
          )}
        </Button>
        <Button variant="destructive" onClick={handleLeave}>
          <LeaveIcon /> Leave
        </Button>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: ConnectionStatus }) {
  const styles: Record<ConnectionStatus, string> = {
    connecting:
      "bg-yellow-600/20 text-yellow-400 border border-yellow-500/30",
    connected: "bg-green-600/20 text-green-400 border border-green-500/30",
    disconnected:
      "bg-gray-600/20 text-gray-400 border border-gray-500/30",
    error: "bg-red-600/20 text-red-400 border border-red-500/30",
  };

  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      {status === "connecting" && "Connecting..."}
      {status === "connected" && "Connected"}
      {status === "disconnected" && "Disconnected"}
      {status === "error" && "Error"}
    </span>
  );
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function MicIcon() {
  return (
    <svg
      className="h-4 w-4 mr-1.5"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z"
      />
    </svg>
  );
}

function MicOffIcon() {
  return (
    <svg
      className="h-4 w-4 mr-1.5"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m2.25 2.25 19.5 19.5M12 18.75a6 6 0 0 0 5.933-5.138M15.75 9V4.5a3.75 3.75 0 1 0-7.5 0v4.875M9 12.75a3 3 0 0 0 3 3m0 0v3.75m-3.75 0h7.5"
      />
    </svg>
  );
}

/** Small mic-off icon for participant card overlays */
function MicOffIconSmall() {
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
        d="m2.25 2.25 19.5 19.5M12 18.75a6 6 0 0 0 5.933-5.138M15.75 9V4.5a3.75 3.75 0 1 0-7.5 0v4.875M9 12.75a3 3 0 0 0 3 3m0 0v3.75m-3.75 0h7.5"
      />
    </svg>
  );
}

/** Transcript/document icon for sidebar header */
function TranscriptIcon() {
  return (
    <svg
      className="h-3.5 w-3.5 text-gray-400"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
      />
    </svg>
  );
}

/** Leave/exit door icon */
function LeaveIcon() {
  return (
    <svg
      className="h-4 w-4 mr-1.5"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9"
      />
    </svg>
  );
}
