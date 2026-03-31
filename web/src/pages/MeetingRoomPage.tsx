import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { getMeetingToken } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import type {
  TranscriptSegment,
  Participant,
  GatewayMessage,
  TtsAudioPayload,
  ChatMessage,
  TurnQueueEntry,
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
type RightTab = "transcript" | "chat";

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

function isAgentParticipant(p: Participant): boolean {
  return p.role === "agent" || p.role.toLowerCase().includes("agent");
}

export function MeetingRoomPage() {
  const { id: meetingId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [handRaised, setHandRaised] = useState(false);
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [speakingNames, setSpeakingNames] = useState<Set<string>>(new Set());
  const [activeSpeaker, setActiveSpeaker] = useState<{ id: string; name: string } | null>(null);
  const [turnQueue, setTurnQueue] = useState<TurnQueueEntry[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [rightTab, setRightTab] = useState<RightTab>("transcript");
  const [yourTurnAlert, setYourTurnAlert] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const playbackContextRef = useRef<AudioContext | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll transcript panel
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  // Auto-scroll chat panel
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Clear "your turn" alert after 5 seconds
  useEffect(() => {
    if (!yourTurnAlert) return;
    const t = setTimeout(() => setYourTurnAlert(false), 5000);
    return () => clearTimeout(t);
  }, [yourTurnAlert]);

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
    if (playbackContextRef.current) {
      playbackContextRef.current.close();
      playbackContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const playTtsAudio = useCallback(async (payload: TtsAudioPayload) => {
    const { speaker_name, data, format } = payload;

    // Decode base64 → ArrayBuffer
    const binary = atob(data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const audioBuffer = bytes.buffer;

    // Lazy-create a playback AudioContext (separate from the capture context)
    if (!playbackContextRef.current) {
      playbackContextRef.current = new AudioContext();
    }
    const ctx = playbackContextRef.current;

    // Resume context if suspended (browser autoplay policy)
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    let decoded: AudioBuffer;
    if (format === "pcm_s16le") {
      // Raw signed 16-bit little-endian PCM — convert manually
      const pcm16 = new Int16Array(audioBuffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7fff);
      }
      decoded = ctx.createBuffer(1, float32.length, ctx.sampleRate);
      decoded.copyToChannel(float32, 0);
    } else {
      // WAV / MP3 / any other container — let the browser decode it
      try {
        decoded = await ctx.decodeAudioData(audioBuffer);
      } catch (err) {
        console.error("[TTS] decodeAudioData failed:", err);
        return;
      }
    }

    // Mark speaker as active, play, then clear
    setSpeakingNames((prev) => new Set([...prev, speaker_name]));
    const source = ctx.createBufferSource();
    source.buffer = decoded;
    source.connect(ctx.destination);
    source.onended = () => {
      setSpeakingNames((prev) => {
        const next = new Set(prev);
        next.delete(speaker_name);
        return next;
      });
    };
    source.start();
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
          speaker_name: msg.speaker_name ?? null,
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
      case "event":
        if (msg.event_type === "tts.audio") {
          void playTtsAudio(msg.payload as unknown as TtsAudioPayload);
        }
        break;
      case "turn.speaker.changed":
        if (msg.speaker_id && msg.speaker_name) {
          setActiveSpeaker({ id: msg.speaker_id, name: msg.speaker_name });
        } else {
          setActiveSpeaker(null);
        }
        break;
      case "turn.queue.updated":
        setTurnQueue(msg.queue);
        break;
      case "turn.your_turn":
        setYourTurnAlert(true);
        setHandRaised(false);
        break;
      case "chat": {
        const cm: ChatMessage = {
          id: `${msg.sender_id}-${msg.timestamp}`,
          sender_id: msg.sender_id,
          sender_name: msg.sender_name,
          text: msg.text,
          timestamp: msg.timestamp,
          is_agent: msg.is_agent,
        };
        setChatMessages((prev) => [...prev, cm]);
        // Switch to chat tab when an agent sends a message
        if (msg.is_agent) {
          setRightTab("chat");
        }
        break;
      }
    }
  }, [playTtsAudio]);

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
        let stream: MediaStream;
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              sampleRate: { ideal: SAMPLE_RATE },
              channelCount: { ideal: 1 },
              echoCancellation: true,
              noiseSuppression: true,
            },
          });
        } catch {
          // Fallback: accept any audio device
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }
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
          let message = "Failed to connect";
          if (err instanceof DOMException) {
            switch (err.name) {
              case "NotFoundError":
                message = "No microphone found. Please connect a microphone and try again.";
                break;
              case "NotAllowedError":
                message = "Microphone permission denied. Please allow microphone access and reload.";
                break;
              case "NotReadableError":
                message = "Microphone is in use by another application.";
                break;
              default:
                message = err.message;
            }
          } else if (err instanceof Error) {
            message = err.message;
          }
          setError(message);
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

  function toggleHand() {
    const next = !handRaised;
    setHandRaised(next);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: next ? "raise_hand" : "lower_hand" }));
    }
  }

  const otherParticipants = participants.filter((p) => p.id !== user?.id);
  const totalCount = otherParticipants.length + 1;

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-3">
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
        <div className="mb-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Your turn alert */}
      {yourTurnAlert && (
        <div className="mb-3 rounded-lg border border-emerald-600 bg-emerald-900/40 px-4 py-2.5 text-sm text-emerald-300 flex items-center gap-2 animate-pulse">
          <MicIcon />
          <span className="font-semibold">You have the floor!</span>
        </div>
      )}

      {/* Active speaker strip */}
      {activeSpeaker && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-emerald-700/50 bg-emerald-950/40 px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-gray-400">Speaking:</span>
          <span className="text-xs font-semibold text-emerald-300">{activeSpeaker.name}</span>
        </div>
      )}

      {/* Turn queue strip — shown only when there are queued speakers */}
      {turnQueue.length > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-700/40 bg-amber-950/30 px-3 py-2">
          <HandIcon className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
          <span className="text-xs text-gray-400 flex-shrink-0">Queue:</span>
          <div className="flex items-center gap-1.5 flex-wrap">
            {turnQueue.map((entry, i) => (
              <span
                key={entry.participant_id}
                className="inline-flex items-center gap-1 rounded-full bg-amber-900/50 border border-amber-700/50 px-2 py-0.5 text-xs text-amber-300"
              >
                <span className="text-amber-500">{i + 1}.</span>
                {entry.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Main content: participants (main) + sidebar (transcript/chat) */}
      <div className="flex flex-col md:flex-row flex-1 gap-4 min-h-0">
        {/* Participants grid — main panel */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-gray-800 bg-gray-900/50 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">
            Participants ({totalCount})
          </h2>
          <div className={`grid ${getGridClasses(totalCount)} gap-4`}>
            {/* Current user card */}
            <div className={`relative flex flex-col items-center justify-center ${getTileHeight(totalCount)} w-full rounded-xl border border-emerald-700/50 bg-gray-900/50 p-4`}>
              <div className="relative mb-3">
                <div className={`${getAvatarSize(totalCount)} rounded-full bg-emerald-600 flex items-center justify-center font-semibold text-white`}>
                  {user?.name?.charAt(0).toUpperCase() ?? "?"}
                </div>
                {!isMuted && (
                  <div className={`absolute inset-0 ${getAvatarSize(totalCount)} rounded-full border-2 border-green-400 animate-pulse`} />
                )}
              </div>
              <p className="text-lg font-medium text-gray-50 truncate max-w-full">
                {user?.name ?? "You"}
              </p>
              <p className="text-sm text-gray-400">You</p>
              {handRaised && (
                <div className="absolute top-3 left-3 text-amber-400" title="Hand raised">
                  <HandIcon className="h-4 w-4" />
                </div>
              )}
              {isMuted && (
                <div className="absolute top-3 right-3 text-red-400" title="Muted">
                  <MicOffIconSmall />
                </div>
              )}
            </div>

            {/* Other participants */}
            {otherParticipants.map((p) => {
              const isAgent = isAgentParticipant(p);
              const isActive = activeSpeaker?.id === p.id;
              const isSpeakingViaTts = speakingNames.has(p.name);
              return (
                <div
                  key={p.id}
                  className={`relative flex flex-col items-center justify-center ${getTileHeight(totalCount)} w-full rounded-xl border p-4 transition-colors ${
                    isActive || isSpeakingViaTts
                      ? "border-emerald-500/60 bg-emerald-950/30"
                      : isAgent
                        ? "border-violet-700/40 bg-gray-900/50"
                        : "border-gray-800 bg-gray-900/50"
                  }`}
                >
                  <div className="relative mb-3">
                    {p.avatar_url ? (
                      <img
                        src={p.avatar_url}
                        alt={p.name}
                        className={`${getAvatarSize(totalCount)} rounded-full object-cover`}
                      />
                    ) : (
                      <div className={`${getAvatarSize(totalCount)} rounded-full flex items-center justify-center font-semibold ${
                        isAgent
                          ? "bg-violet-700 text-violet-100"
                          : "bg-gray-700 text-gray-300"
                      }`}>
                        {isAgent ? <BotIcon /> : p.name.charAt(0).toUpperCase()}
                      </div>
                    )}
                    {(isActive || isSpeakingViaTts || p.is_speaking) && (
                      <div className={`absolute inset-0 ${getAvatarSize(totalCount)} rounded-full border-2 border-green-400 animate-pulse`} />
                    )}
                  </div>
                  <p className="text-lg font-medium text-gray-200 truncate max-w-full">
                    {p.name}
                  </p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <p className="text-sm text-gray-400">
                      {isSpeakingViaTts ? (
                        <span className="text-green-400">Speaking...</span>
                      ) : (
                        p.role
                      )}
                    </p>
                    {isAgent && (
                      <span className="inline-flex items-center rounded-full bg-violet-900/60 border border-violet-600/40 px-1.5 py-0 text-[10px] font-medium text-violet-300">
                        AI
                      </span>
                    )}
                  </div>
                  {p.is_muted && (
                    <div className="absolute top-3 right-3 text-red-400" title="Muted">
                      <MicOffIconSmall />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right sidebar — tabbed: Transcript | Chat */}
        <div className="w-full md:w-80 md:flex-shrink-0 flex flex-col rounded-lg border border-gray-800 bg-gray-900/50 overflow-hidden">
          {/* Tab bar */}
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setRightTab("transcript")}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
                rightTab === "transcript"
                  ? "text-emerald-400 border-b-2 border-emerald-500 -mb-px bg-gray-800/50"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              <TranscriptIcon />
              Transcript
            </button>
            <button
              onClick={() => setRightTab("chat")}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors relative ${
                rightTab === "chat"
                  ? "text-emerald-400 border-b-2 border-emerald-500 -mb-px bg-gray-800/50"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              <ChatIcon />
              Chat
              {/* Unread indicator */}
              {rightTab !== "chat" && chatMessages.length > 0 && (
                <span className="absolute top-1.5 right-3 h-1.5 w-1.5 rounded-full bg-emerald-400" />
              )}
            </button>
          </div>

          {/* Transcript panel */}
          {rightTab === "transcript" && (
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
                    {seg.speaker_name ?? seg.speaker_id}
                  </span>
                  <span className="text-gray-600 mx-1 text-[10px]">
                    {formatTimestamp(seg.start_time)}
                  </span>
                  <span>{seg.text}</span>
                </div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
          )}

          {/* Chat panel */}
          {rightTab === "chat" && (
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
              {chatMessages.length === 0 && (
                <p className="text-xs text-gray-500 text-center py-6">
                  No messages yet...
                </p>
              )}
              {chatMessages.map((msg) => {
                const isOwn = msg.sender_id === user?.id;
                return (
                  <div key={msg.id} className={`flex flex-col gap-0.5 ${isOwn ? "items-end" : "items-start"}`}>
                    <div className="flex items-center gap-1">
                      {msg.is_agent && (
                        <span className="inline-flex items-center rounded-full bg-violet-900/60 border border-violet-600/40 px-1.5 py-0 text-[10px] font-medium text-violet-300">
                          AI
                        </span>
                      )}
                      <span className={`text-[10px] font-medium ${msg.is_agent ? "text-violet-400" : isOwn ? "text-emerald-400" : "text-blue-400"}`}>
                        {isOwn ? "You" : msg.sender_name}
                      </span>
                      <span className="text-[10px] text-gray-600">
                        {formatChatTime(msg.timestamp)}
                      </span>
                    </div>
                    <div className={`max-w-[90%] rounded-lg px-2.5 py-1.5 text-xs ${
                      isOwn
                        ? "bg-emerald-800/50 text-emerald-100 border border-emerald-700/40"
                        : msg.is_agent
                          ? "bg-violet-900/40 text-violet-100 border border-violet-700/40"
                          : "bg-gray-800 text-gray-200 border border-gray-700"
                    }`}>
                      {msg.text}
                    </div>
                  </div>
                );
              })}
              <div ref={chatEndRef} />
            </div>
          )}
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
        <Button
          variant="outline"
          onClick={toggleHand}
          className={handRaised ? "border-amber-500/60 text-amber-400 hover:bg-amber-900/20" : ""}
        >
          <HandIcon className="h-4 w-4 mr-1.5" />
          {handRaised ? "Lower Hand" : "Raise Hand"}
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

function formatChatTime(timestamp: number): string {
  const d = new Date(timestamp * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

/** Transcript/document icon for sidebar tab */
function TranscriptIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
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

/** Chat bubble icon for sidebar tab */
function ChatIcon() {
  return (
    <svg
      className="h-3.5 w-3.5"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z"
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

/** Raised hand icon for turn queue and hand raise button */
function HandIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className ?? "h-4 w-4"}
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

/** Sparkle/bot icon for AI agent avatars */
function BotIcon() {
  return (
    <svg
      className="h-10 w-10 text-violet-200"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
      />
    </svg>
  );
}
