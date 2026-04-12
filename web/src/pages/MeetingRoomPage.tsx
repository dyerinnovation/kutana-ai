import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  RoomEvent,
  Track,
  type Room as LkRoom,
  type RemoteParticipant as LkRemoteParticipant,
} from "livekit-client";
import { useAuth } from "@/hooks/useAuth";
import { useLiveKitRoom } from "@/hooks/useLiveKitRoom";
import {
  getAgentSessions,
  getMeetingToken,
  retryAgentSession,
} from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import { SpeakerQueuePanel } from "@/components/meeting/SpeakerQueuePanel";
import { showToast } from "@/components/Toast";
import type {
  AgentSessionInfo,
  AgentWarmingState,
  TranscriptSegment,
  Participant,
  GatewayMessage,
  ChatMessage,
  TurnQueueEntry,
  TurnQueuePayload,
  TurnSpeakerChangedPayload,
} from "@/types";

const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
// If VITE_WS_BASE_URL is set (e.g. "https://ws-dev.kutana.ai"), use that host
// and connect to /connect at root (public WS ingress has no /human rewrite).
// Otherwise fall back to same-origin /human/connect (LAN dev).
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL;
const HUMAN_WS_BASE = WS_BASE_URL
  ? `${WS_BASE_URL.replace(/^https?:/, wsProto)}/connect`
  : `${wsProto}//${window.location.host}/human/connect`;

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";
type RightTab = "transcript" | "chat" | "agents";

interface AgentActivityEvent {
  id: string;
  agent_name: string;
  event_type: "message" | "tool_use" | "error" | "status";
  content: string;
  timestamp: number;
}

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

  const lk = useLiveKitRoom(meetingId ?? null);

  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [handRaised, setHandRaised] = useState(false);
  const [canPlaybackAudio, setCanPlaybackAudio] = useState(true);
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [speakingNames, setSpeakingNames] = useState<Set<string>>(new Set());
  const [activeSpeaker, setActiveSpeaker] = useState<{ id: string; name: string } | null>(null);
  const [turnQueue, setTurnQueue] = useState<TurnQueueEntry[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [agentEvents, setAgentEvents] = useState<AgentActivityEvent[]>([]);
  const [agentSessions, setAgentSessions] = useState<
    Record<string, AgentSessionInfo>
  >({});
  const [rightTab, setRightTab] = useState<RightTab>("transcript");
  const [yourTurnAlert, setYourTurnAlert] = useState(false);
  const [chatInput, setChatInput] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const agentEndRef = useRef<HTMLDivElement>(null);
  const participantsRef = useRef<Participant[]>([]);

  // Keep participantsRef in sync for use in event handlers
  useEffect(() => {
    participantsRef.current = participants;
  }, [participants]);

  // Auto-scroll transcript panel
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  // Auto-scroll chat panel
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Auto-scroll agent activity panel
  useEffect(() => {
    agentEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [agentEvents]);

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
            const p: Participant = {
              id: msg.participant_id,
              name: msg.name,
              role: msg.role,
              is_muted: false,
              capabilities: msg.capabilities,
            };
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
      case "event": {
        const evPayload = msg.payload as Record<string, unknown>;
        if (msg.event_type === "chat.message.received") {
          const cm: ChatMessage = {
            id: `${evPayload.sender_id}-${evPayload.timestamp ?? Date.now()}`,
            sender_id: evPayload.sender_id as string,
            sender_name: evPayload.sender_name as string,
            text: (evPayload.content ?? evPayload.text) as string,
            timestamp: (evPayload.timestamp as number) ?? Date.now() / 1000,
            is_agent: (evPayload.is_agent as boolean) ?? false,
          };
          if (cm.sender_id !== user?.id) {
            setChatMessages((prev) => [...prev, cm]);
            if (cm.is_agent) setRightTab("chat");
          }
        } else if (msg.event_type === "turn.speaker.changed") {
          const tp = evPayload as unknown as TurnSpeakerChangedPayload;
          if (tp.new_speaker_id) {
            setActiveSpeaker(() => {
              const name = participantsRef.current.find((p) => p.id === tp.new_speaker_id)?.name ?? "Speaker";
              return { id: tp.new_speaker_id!, name };
            });
          } else {
            setActiveSpeaker(null);
          }
        } else if (msg.event_type === "turn.queue.updated") {
          const qp = evPayload as unknown as TurnQueuePayload;
          const enriched = qp.queue.map((entry) => ({
            ...entry,
            name: participantsRef.current.find((p) => p.id === entry.participant_id)?.name ?? "Unknown",
          }));
          setTurnQueue(enriched);
          if (qp.active_speaker_id) {
            setActiveSpeaker((prev) => {
              if (prev?.id === qp.active_speaker_id) return prev;
              const name = participantsRef.current.find((p) => p.id === qp.active_speaker_id)?.name ?? "Speaker";
              return { id: qp.active_speaker_id!, name };
            });
          }
        } else if (msg.event_type === "turn.your_turn") {
          setYourTurnAlert(true);
          setHandRaised(false);
        } else if (msg.event_type === "turn.speaking.started") {
          const sp = evPayload as { participant_id: string };
          setSpeakingNames((prev) => {
            const name = participantsRef.current.find((p) => p.id === sp.participant_id)?.name;
            if (name) return new Set([...prev, name]);
            return prev;
          });
        } else if (msg.event_type === "turn.speaker.finished") {
          const fp = evPayload as { participant_id: string };
          setSpeakingNames((prev) => {
            const name = participantsRef.current.find((p) => p.id === fp.participant_id)?.name;
            if (name) {
              const next = new Set(prev);
              next.delete(name);
              return next;
            }
            return prev;
          });
        } else if (msg.event_type === "agent.message") {
          const agentEvt: AgentActivityEvent = {
            id: `agent-msg-${Date.now()}-${Math.random()}`,
            agent_name: (evPayload.agent_name as string) ?? "Agent",
            event_type: "message",
            content: (evPayload.content ?? evPayload.text) as string,
            timestamp: (evPayload.timestamp as number) ?? Date.now() / 1000,
          };
          setAgentEvents((prev) => [...prev, agentEvt]);
          // Also add to chat sidebar attributed to agent name
          setChatMessages((prev) => [...prev, {
            id: agentEvt.id,
            sender_id: "agent",
            sender_name: agentEvt.agent_name,
            text: agentEvt.content,
            timestamp: agentEvt.timestamp,
            is_agent: true,
          }]);
        } else if (msg.event_type === "agent.mcp_tool_use") {
          const toolEvt: AgentActivityEvent = {
            id: `agent-tool-${Date.now()}-${Math.random()}`,
            agent_name: (evPayload.agent_name as string) ?? "Agent",
            event_type: "tool_use",
            content: (evPayload.tool_name as string) ?? "processing",
            timestamp: (evPayload.timestamp as number) ?? Date.now() / 1000,
          };
          setAgentEvents((prev) => [...prev, toolEvt]);
          setRightTab("agents");
        } else if (msg.event_type === "session.error") {
          const errEvt: AgentActivityEvent = {
            id: `agent-err-${Date.now()}-${Math.random()}`,
            agent_name: (evPayload.agent_name as string) ?? "Agent",
            event_type: "error",
            content: (evPayload.message ?? evPayload.error) as string,
            timestamp: (evPayload.timestamp as number) ?? Date.now() / 1000,
          };
          setAgentEvents((prev) => [...prev, errEvt]);
          setRightTab("agents");
        } else if (msg.event_type === "session.status_idle") {
          const idleEvt: AgentActivityEvent = {
            id: `agent-idle-${Date.now()}-${Math.random()}`,
            agent_name: (evPayload.agent_name as string) ?? "Agent",
            event_type: "status",
            content: "Waiting for input...",
            timestamp: (evPayload.timestamp as number) ?? Date.now() / 1000,
          };
          setAgentEvents((prev) => [...prev, idleEvt]);
        } else if (
          msg.event_type === "agent.session.warmed" ||
          msg.event_type === "agent.session.failed" ||
          msg.event_type === "agent.session.stopped"
        ) {
          const templateId = evPayload.template_id as string | undefined;
          if (!templateId) break;
          const templateName =
            (evPayload.template_name as string | undefined) ??
            (evPayload.agent_name as string | undefined) ??
            "Agent";
          const nextState: AgentWarmingState =
            msg.event_type === "agent.session.warmed"
              ? "ready"
              : msg.event_type === "agent.session.failed"
                ? "failed"
                : "stopped";
          setAgentSessions((prev) => ({
            ...prev,
            [templateId]: {
              template_id: templateId,
              template_name: prev[templateId]?.template_name ?? templateName,
              state: nextState,
              hosted_session_id:
                (evPayload.hosted_session_id as string | null | undefined) ??
                prev[templateId]?.hosted_session_id ??
                null,
              error:
                nextState === "failed"
                  ? ((evPayload.error as string | undefined) ??
                    (evPayload.message as string | undefined) ??
                    "Agent failed to start")
                  : null,
            },
          }));
        }
        break;
      }
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
  }, [user?.id]);

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

        // Seed per-agent warming state from the server before the WS opens
        // so the panel renders `warming` chips immediately on entry.
        getAgentSessions(meetingId!)
          .then((items) => {
            if (cancelled) return;
            setAgentSessions(() => {
              const next: Record<string, AgentSessionInfo> = {};
              for (const item of items) {
                next[item.template_id] = item;
              }
              return next;
            });
          })
          .catch(() => {
            // Best-effort — the panel will still populate from WS events.
          });

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

      } catch (err) {
        console.error("[Meeting] connect() error:", err);
        if (!cancelled) {
          setStatus("error");
          let message = "Failed to connect";
          if (err instanceof Error) {
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

  // Track LiveKit autoplay gate
  useEffect(() => {
    if (!lk.room || lk.status !== "connected") return;
    setCanPlaybackAudio(lk.room.canPlaybackAudio);
    const handler = () => setCanPlaybackAudio(lk.room!.canPlaybackAudio);
    lk.room.on(RoomEvent.AudioPlaybackStatusChanged, handler);
    return () => { lk.room?.off(RoomEvent.AudioPlaybackStatusChanged, handler); };
  }, [lk.room, lk.status]);

  function handleLeave() {
    cleanup();
    navigate("/meetings");
  }

  function finishedSpeaking() {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "finished_speaking" }));
    }
    setYourTurnAlert(false);
  }

  function sendChat() {
    if (!chatInput.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "chat", text: chatInput.trim() }));
    setChatMessages((prev) => [...prev, {
      id: `self-${Date.now()}`,
      sender_id: user?.id ?? "unknown",
      sender_name: user?.name ?? "You",
      text: chatInput.trim(),
      timestamp: Date.now() / 1000,
      is_agent: false,
    }]);
    setChatInput("");
  }

  function toggleHand() {
    const next = !handRaised;
    setHandRaised(next);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: next ? "raise_hand" : "lower_hand" }));
    }
  }

  async function handleRetryAgent(templateId: string) {
    if (!meetingId) return;
    // Optimistically flip back to warming so the spinner reappears.
    setAgentSessions((prev) => {
      const existing = prev[templateId];
      if (!existing) return prev;
      return {
        ...prev,
        [templateId]: { ...existing, state: "warming", error: null },
      };
    });
    try {
      await retryAgentSession(meetingId, templateId);
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : "Failed to retry agent",
      );
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

      {/* LiveKit status banners */}
      {lk.status === "reconnecting" && (
        <div className="mb-3 rounded-lg border border-amber-700 bg-amber-950/50 px-4 py-2.5 text-sm text-amber-400">
          Audio reconnecting...
        </div>
      )}
      {lk.status === "error" && lk.error && (
        <div className="mb-3 rounded-lg border border-red-800 bg-red-950/50 px-4 py-2.5 text-sm text-red-400">
          Audio error: {lk.error.message}
        </div>
      )}

      {/* Autoplay gate — browser blocked audio autoplay */}
      {!canPlaybackAudio && (
        <button
          type="button"
          onClick={() => lk.room?.startAudio()}
          className="mb-3 w-full rounded-lg border border-blue-700 bg-blue-950/50 px-4 py-2.5 text-sm text-blue-300 hover:bg-blue-900/50 transition-colors text-left"
        >
          Click to enable audio playback
        </button>
      )}

      {/* Your turn alert */}
      {yourTurnAlert && (
        <div className="mb-3 rounded-lg border border-emerald-600 bg-emerald-900/40 px-4 py-2.5 text-sm text-emerald-300 flex items-center gap-2 animate-pulse">
          <MicIcon />
          <span className="font-semibold">You have the floor!</span>
        </div>
      )}

      {/* Speaker queue panel */}
      <SpeakerQueuePanel
        activeSpeaker={activeSpeaker}
        queue={turnQueue}
        participants={participants}
        currentUserId={user?.id}
        isMyTurn={yourTurnAlert || activeSpeaker?.id === user?.id}
        onFinishedSpeaking={finishedSpeaking}
      />

      {/* Main content: participants (main) + sidebar (transcript/chat) */}
      <div className="flex flex-col md:flex-row flex-1 gap-4 min-h-0">
        {/* Participants grid — main panel */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-gray-800 bg-gray-900/50 p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">
            Participants ({totalCount})
          </h2>

          {/* Video tiles — only shown when VITE_ENABLE_VIDEO=1 */}
          {import.meta.env.VITE_ENABLE_VIDEO === "1" && lk.room && (
            <div className="flex flex-wrap gap-2 mb-4">
              <LocalVideoTile room={lk.room} />
              {lk.participants.map((p) => (
                <RemoteVideoTile key={p.identity} participant={p} />
              ))}
            </div>
          )}

          <div className={`grid ${getGridClasses(totalCount)} gap-4`}>
            {/* Current user card */}
            <div className={`relative flex flex-col items-center justify-center ${getTileHeight(totalCount)} w-full rounded-xl border border-emerald-700/50 bg-gray-900/50 p-4`}>
              <div className="relative mb-3">
                <div className={`${getAvatarSize(totalCount)} rounded-full bg-emerald-600 flex items-center justify-center font-semibold text-white`}>
                  {user?.name?.charAt(0).toUpperCase() ?? "?"}
                </div>
                {lk.localMicEnabled && (
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
              {!lk.localMicEnabled && (
                <div className="absolute top-3 right-3 text-red-400" title="Muted">
                  <MicOffIconSmall />
                </div>
              )}
            </div>

            {/* Other participants */}
            {otherParticipants.map((p) => {
              const isAgent = isAgentParticipant(p);
              const isActive = activeSpeaker?.id === p.id;
              const isSpeakingViaTts =
                speakingNames.has(p.name) ||
                lk.activeSpeakerIdentities.includes(p.id);
              const hasHandRaised = turnQueue.some((q) => q.participant_id === p.id);
              return (
                <div
                  key={p.id}
                  className={`relative flex flex-col items-center justify-center ${getTileHeight(totalCount)} w-full rounded-xl border p-4 transition-colors ${
                    isActive || isSpeakingViaTts
                      ? "border-emerald-500/60 bg-emerald-950/30"
                      : hasHandRaised
                        ? "border-amber-600/40 bg-amber-950/20"
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
                  {hasHandRaised && (
                    <div className="absolute top-3 left-3 text-amber-400" title="Hand raised">
                      <HandIcon className="h-4 w-4" />
                    </div>
                  )}
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

        {/* Right sidebar — tabbed: Transcript | Chat | Agents */}
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
            <button
              onClick={() => setRightTab("agents")}
              className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors relative ${
                rightTab === "agents"
                  ? "text-violet-400 border-b-2 border-violet-500 -mb-px bg-gray-800/50"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              <AgentActivityIcon />
              Agents
              {/* Activity indicator */}
              {rightTab !== "agents" && agentEvents.length > 0 && (
                <span className="absolute top-1.5 right-2 h-1.5 w-1.5 rounded-full bg-violet-400" />
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

          {/* Agent activity panel */}
          {rightTab === "agents" && (
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
              {/* Per-agent lifecycle chips (warming → ready / failed / stopped) */}
              {Object.keys(agentSessions).length > 0 && (
                <div className="space-y-1.5 pb-2 border-b border-gray-800">
                  {Object.values(agentSessions).map((session) => (
                    <AgentSessionChip
                      key={session.template_id}
                      session={session}
                      onRetry={() => handleRetryAgent(session.template_id)}
                    />
                  ))}
                </div>
              )}
              {agentEvents.length === 0 && Object.keys(agentSessions).length === 0 && (
                <p className="text-xs text-gray-500 text-center py-6">
                  No agents selected for this meeting.
                </p>
              )}
              {agentEvents.map((evt) => (
                <div key={evt.id} className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-1">
                    <span className="inline-flex items-center rounded-full bg-violet-900/60 border border-violet-600/40 px-1.5 py-0 text-[10px] font-medium text-violet-300">
                      AI
                    </span>
                    <span className="text-[10px] font-medium text-violet-400">
                      {evt.agent_name}
                    </span>
                    <span className="text-[10px] text-gray-600">
                      {formatChatTime(evt.timestamp)}
                    </span>
                  </div>
                  <div className={`max-w-[95%] rounded-lg px-2.5 py-1.5 text-xs ${
                    evt.event_type === "error"
                      ? "bg-red-900/40 text-red-200 border border-red-700/40"
                      : evt.event_type === "tool_use"
                        ? "bg-gray-800/80 text-gray-300 border border-gray-700 italic"
                        : evt.event_type === "status"
                          ? "bg-gray-800/50 text-gray-400 border border-gray-700/50"
                          : "bg-violet-900/40 text-violet-100 border border-violet-700/40"
                  }`}>
                    {evt.event_type === "tool_use" && (
                      <span className="text-violet-400 mr-1">
                        <ToolIcon />
                      </span>
                    )}
                    {evt.event_type === "error" && "Error: "}
                    {evt.event_type === "tool_use"
                      ? `${evt.agent_name} is using ${evt.content}...`
                      : evt.content}
                  </div>
                </div>
              ))}
              <div ref={agentEndRef} />
            </div>
          )}
          <form
            onSubmit={(e) => { e.preventDefault(); sendChat(); }}
            className="flex gap-2 p-3 border-t border-gray-700"
          >
            <input
              className="flex-1 rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-50 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Type a message..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
            />
            <Button type="submit" size="sm" disabled={!chatInput.trim()}>Send</Button>
          </form>
        </div>
      </div>

      {/* Sticky bottom controls bar */}
      <div className="mt-4 flex items-center justify-center gap-4 border-t border-gray-800 pt-4">
        <Button
          variant={!lk.localMicEnabled ? "destructive" : "outline"}
          onClick={() => void lk.enableMic(!lk.localMicEnabled)}
        >
          {!lk.localMicEnabled ? (
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
        {(yourTurnAlert || activeSpeaker?.id === user?.id) && (
          <Button
            variant="outline"
            onClick={finishedSpeaking}
            className="border-emerald-500/60 text-emerald-400 hover:bg-emerald-900/20"
          >
            <CheckIcon /> Done Speaking
          </Button>
        )}
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

/** Checkmark icon for "done speaking" button */
function CheckIcon() {
  return (
    <svg className="h-4 w-4 mr-1.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
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

/** Agent activity sparkle icon for sidebar tab */
function AgentActivityIcon() {
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
        d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z"
      />
    </svg>
  );
}

/** Wrench/tool icon for MCP tool use activity */
function ToolIcon() {
  return (
    <svg
      className="inline h-3 w-3"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z"
      />
    </svg>
  );
}

/** Per-agent lifecycle chip shown in the meeting room's Agents tab. */
function AgentSessionChip({
  session,
  onRetry,
}: {
  session: AgentSessionInfo;
  onRetry: () => void;
}) {
  const label: Record<AgentWarmingState, string> = {
    warming: `Warming ${session.template_name}...`,
    ready: "Active",
    failed: session.error ?? "Failed to start",
    stopped: "Stopped — no participants",
  };
  const containerClass: Record<AgentWarmingState, string> = {
    warming: "border-violet-700/40 bg-violet-950/30 text-violet-200",
    ready: "border-emerald-700/40 bg-emerald-950/30 text-emerald-200",
    failed: "border-red-700/40 bg-red-950/40 text-red-200",
    stopped: "border-gray-700 bg-gray-900/60 text-gray-400",
  };
  return (
    <div
      data-testid={`agent-chip-${session.template_id}`}
      data-state={session.state}
      className={`flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-xs ${containerClass[session.state]}`}
    >
      <span
        data-testid={`agent-chip-${session.template_id}-state-${session.state}`}
        className="sr-only"
      >
        {session.state}
      </span>
      <div className="mt-0.5 flex h-4 w-4 items-center justify-center">
        {session.state === "warming" && <SpinnerIcon />}
        {session.state === "ready" && <CheckBadgeIcon />}
        {session.state === "failed" && <ErrorIcon />}
        {session.state === "stopped" && <PauseIcon />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-gray-100 truncate">
          {session.template_name}
        </div>
        <div className="opacity-80 truncate">{label[session.state]}</div>
      </div>
      {session.state === "failed" && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-red-600/50 bg-red-900/40 px-2 py-0.5 text-[11px] font-medium text-red-100 hover:bg-red-900/60"
        >
          Retry
        </button>
      )}
    </div>
  );
}

function SpinnerIcon() {
  return (
    <svg className="h-3.5 w-3.5 animate-spin text-violet-300" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" />
      <path
        d="M22 12a10 10 0 0 1-10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function CheckBadgeIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-emerald-400" viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-red-400" viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m0 3.75h.008v.008H12v-.008Zm0-15a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z"
      />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-gray-500" viewBox="0 0 24 24" fill="none" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25v13.5m-7.5-13.5v13.5" />
    </svg>
  );
}

/** Local camera video tile — rendered only when VITE_ENABLE_VIDEO=1 */
function LocalVideoTile({ room }: { room: LkRoom }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const pub = room.localParticipant.getTrackPublication(Track.Source.Camera);
    const track = pub?.track;
    if (!track) return;
    track.attach(el);
    return () => { track.detach(el); };
  }, [room]);
  return (
    <video
      ref={videoRef}
      autoPlay
      muted
      playsInline
      className="w-32 h-24 rounded-lg object-cover bg-gray-800 border border-gray-700"
    />
  );
}

/** Remote participant camera video tile — rendered only when VITE_ENABLE_VIDEO=1 */
function RemoteVideoTile({ participant }: { participant: LkRemoteParticipant }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const pub = participant.getTrackPublication(Track.Source.Camera);
  useEffect(() => {
    const el = videoRef.current;
    if (!el || !pub?.track) return;
    pub.track.attach(el);
    return () => { pub.track?.detach(el); };
  }, [pub]);
  if (!pub?.isSubscribed) return null;
  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      className="w-32 h-24 rounded-lg object-cover bg-gray-800 border border-gray-700"
    />
  );
}
