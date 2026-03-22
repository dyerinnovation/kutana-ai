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

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

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
    const msg = JSON.parse(event.data) as GatewayMessage;

    switch (msg.type) {
      case "transcript":
        setTranscripts((prev) => {
          // Replace non-final segment from same speaker, or append
          if (!msg.segment.is_final) {
            const idx = prev.findIndex(
              (s) =>
                s.speaker_id === msg.segment.speaker_id && !s.is_final
            );
            if (idx !== -1) {
              const updated = [...prev];
              updated[idx] = msg.segment;
              return updated;
            }
          }
          return [...prev, msg.segment];
        });
        break;
      case "participant_update":
        setParticipants(msg.participants);
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
      try {
        // 1. Get gateway token
        const { token } = await getMeetingToken(meetingId!);
        if (cancelled) return;

        // 2. Open WebSocket — meeting_id in URL, no join_meeting message needed
        const ws = new WebSocket(
          `${HUMAN_WS_BASE}?token=${token}&meeting_id=${meetingId}`
        );
        wsRef.current = ws;

        // No onopen send needed: server auto-joins on connect and sends "joined"
        ws.onopen = () => {};

        ws.onmessage = handleWsMessage;

        ws.onerror = () => {
          if (!cancelled) {
            setStatus("error");
            setError("WebSocket connection failed");
          }
        };

        ws.onclose = () => {
          if (!cancelled) setStatus("disconnected");
        };

        // 3. Start audio capture
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: SAMPLE_RATE,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
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
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Main transcript area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-4">
          <div>
            <h1 className="text-xl font-bold text-white">Meeting Room</h1>
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
          <div className="mt-4 rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Transcript panel */}
        <div className="mt-4 flex-1 overflow-y-auto rounded-lg border border-gray-800 bg-gray-900/50 p-4 space-y-3">
          {transcripts.length === 0 && status === "connected" && (
            <p className="text-sm text-gray-500 text-center py-8">
              Waiting for speech...
            </p>
          )}
          {transcripts.length === 0 && status === "connecting" && (
            <p className="text-sm text-gray-500 text-center py-8">
              Connecting to meeting...
            </p>
          )}
          {transcripts.map((seg, i) => (
            <div
              key={`${seg.speaker_id}-${seg.start_time}-${i}`}
              className={`text-sm ${seg.is_final ? "text-gray-200" : "text-gray-400 italic"}`}
            >
              <span className="font-medium text-blue-400">
                {seg.speaker_id}
              </span>
              <span className="text-gray-600 mx-2">
                {formatTimestamp(seg.start_time)}
              </span>
              <span>{seg.text}</span>
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>

        {/* Controls */}
        <div className="mt-4 flex items-center justify-center gap-3">
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
            Leave Meeting
          </Button>
        </div>
      </div>

      {/* Sidebar: Participants */}
      <div className="w-64 flex-shrink-0 rounded-lg border border-gray-800 bg-gray-900/50 p-4">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">
          Participants ({participants.length || 1})
        </h2>
        <div className="space-y-2">
          {/* Current user always shown */}
          <div className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm">
            <div className="h-7 w-7 rounded-full bg-blue-600 flex items-center justify-center text-xs font-medium text-white">
              {user?.name?.charAt(0).toUpperCase() ?? "?"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-white text-sm">
                {user?.name ?? "You"}
              </p>
              <p className="text-xs text-gray-500">
                {isMuted ? "Muted" : "Speaking"}
              </p>
            </div>
          </div>

          {participants
            .filter((p) => p.id !== user?.id)
            .map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              >
                <div className="h-7 w-7 rounded-full bg-gray-700 flex items-center justify-center text-xs font-medium text-gray-300">
                  {p.name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-gray-200 text-sm">{p.name}</p>
                  <p className="text-xs text-gray-500">
                    {p.role} {p.is_muted ? "- Muted" : ""}
                  </p>
                </div>
              </div>
            ))}
        </div>
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
