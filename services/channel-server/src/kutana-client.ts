/**
 * Kutana AI WebSocket client for the channel server.
 *
 * Lifecycle:
 *   1. authenticate() — exchanges API key for a gateway JWT (or uses pre-issued token)
 *   2. listMeetings() / createMeeting() — HTTP calls against the API server
 *   3. joinMeeting(meetingId) — opens WebSocket, joins the meeting, starts event forwarding
 *   4. leaveMeeting() — sends leave, closes WebSocket, clears buffers
 *
 * Authentication is required before any operation. WebSocket is only opened
 * when joining a meeting — listing and creating meetings use plain HTTP.
 */

import WebSocket from "ws";
import type { ChannelServerConfig } from "./config.js";
import type {
  AnyExtractedEntity,
  ChannelMessage,
  ChatMessage,
  EntityType,
  GatewayError,
  GatewayEvent,
  InsightPayload,
  JoinedMessage,
  MeetingInfo,
  ParticipantInfo,
  TranscriptSegment,
  TurnQueueStatus,
} from "./types.js";

/** Callback invoked when a channel-worthy event arrives. */
export type ChannelEventCallback = (
  message: ChannelMessage,
) => Promise<void> | void;

/** Injectable WebSocket constructor — allows test code to supply a mock. */
export type WebSocketConstructor = new (
  url: string,
  options?: { rejectUnauthorized?: boolean },
) => WebSocket;

export class KutanaClient {
  private ws: WebSocket | null = null;
  private token: string | null = null;
  private currentMeetingId: string | null = null;
  private connected = false;
  private channelCallback: ChannelEventCallback | null = null;

  private transcriptBuffer: TranscriptSegment[] = [];
  private entityBuffer: AnyExtractedEntity[] = [];
  private chatBuffer: ChatMessage[] = [];
  private participantsBuffer: ParticipantInfo[] = [];
  private lastQueueStatus: TurnQueueStatus | null = null;

  /** Locally-tracked speaking state (updated from gateway events). */
  private isSpeaking = false;
  private isInQueue = false;
  private chatIndex = 0;

  constructor(
    private readonly config: ChannelServerConfig,
    /** Allows injecting a mock WebSocket in tests. */
    private readonly WS: WebSocketConstructor = WebSocket as unknown as WebSocketConstructor,
  ) {}

  // ---------------------------------------------------------------------------
  // Public API — Lifecycle
  // ---------------------------------------------------------------------------

  /** Register a callback that receives channel messages. */
  onChannelMessage(callback: ChannelEventCallback): void {
    this.channelCallback = callback;
  }

  /**
   * Exchange the API key for a gateway JWT.
   * Idempotent — skips if a token is already available.
   */
  async authenticate(): Promise<void> {
    if (this.token) return;

    // If a pre-issued gateway JWT is configured, use it directly.
    if (this.config.kutanaBearerToken) {
      this.token = this.config.kutanaBearerToken;
      process.stderr.write(
        "[channel-server] Using pre-issued bearer token (skipping API-key exchange)\n",
      );
      return;
    }

    const url = `${this.config.kutanaHttpUrl}/api/v1/token/gateway`;
    const resp = await fetch(url, {
      method: "POST",
      headers: { "X-API-Key": this.config.kutanaApiKey },
      ...(this.config.tlsRejectUnauthorized
        ? {}
        : { tls: { rejectUnauthorized: false } }),
    });

    if (!resp.ok) {
      throw new Error(
        `Kutana auth failed: ${resp.status.toString()} ${resp.statusText}`,
      );
    }

    const data = (await resp.json()) as { token: string };
    this.token = data.token;
  }

  /**
   * Join a meeting by ID. Opens a WebSocket to the agent gateway,
   * sends join_meeting, and starts event forwarding.
   *
   * @param meetingId UUID of the meeting to join.
   * @param capabilities Capabilities to request (default: listen, transcribe, data_channel).
   */
  async joinMeeting(
    meetingId: string,
    capabilities: string[] = ["listen", "transcribe", "data_channel"],
  ): Promise<void> {
    if (this.currentMeetingId) {
      throw new Error(
        `Already in meeting ${this.currentMeetingId}. Call leaveMeeting() first.`,
      );
    }
    if (!this.token) {
      // Auto-authenticate if not yet done
      await this.authenticate();
    }
    await this.connectWebSocket(meetingId, capabilities);
  }

  /**
   * Leave the current meeting. Sends leave_meeting, closes the WebSocket,
   * and clears all per-meeting buffers.
   */
  async leaveMeeting(): Promise<void> {
    if (!this.currentMeetingId) return;

    if (this.ws) {
      try {
        this.send({ type: "leave_meeting", reason: "agent_disconnect" });
      } catch {
        // Best-effort — ignore send errors during shutdown
      }
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    const leftMeeting = this.currentMeetingId;
    this.currentMeetingId = null;
    this.resetBuffers();

    this.emit({
      topic: "meeting_lifecycle",
      type: "left",
      content: `<meeting action="left">Left meeting ${leftMeeting}.</meeting>`,
    });
  }

  isConnected(): boolean {
    return this.connected;
  }

  getCurrentMeetingId(): string | null {
    return this.currentMeetingId;
  }

  // ---------------------------------------------------------------------------
  // Public API — HTTP (no WebSocket required)
  // ---------------------------------------------------------------------------

  /** List available meetings from the API server. */
  async listMeetings(): Promise<MeetingInfo[]> {
    if (!this.token) {
      await this.authenticate();
    }

    const url = `${this.config.kutanaHttpUrl}/api/v1/meetings`;
    const resp = await fetch(url, {
      headers: { "X-API-Key": this.config.kutanaApiKey },
      ...(this.config.tlsRejectUnauthorized
        ? {}
        : { tls: { rejectUnauthorized: false } }),
    });

    if (!resp.ok) {
      throw new Error(
        `Failed to list meetings: ${resp.status.toString()} ${resp.statusText}`,
      );
    }

    const data = (await resp.json()) as { items: MeetingInfo[] };
    return data.items;
  }

  /** Create a new meeting via the API server. */
  async createMeeting(title: string): Promise<MeetingInfo> {
    if (!this.token) {
      await this.authenticate();
    }

    const url = `${this.config.kutanaHttpUrl}/api/v1/meetings`;
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        "X-API-Key": this.config.kutanaApiKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title, platform: "kutana" }),
      ...(this.config.tlsRejectUnauthorized
        ? {}
        : { tls: { rejectUnauthorized: false } }),
    });

    if (!resp.ok) {
      throw new Error(
        `Failed to create meeting: ${resp.status.toString()} ${resp.statusText}`,
      );
    }

    return (await resp.json()) as MeetingInfo;
  }

  // ---------------------------------------------------------------------------
  // Public API — Two-way communication (requires active meeting)
  // ---------------------------------------------------------------------------

  async sendChatMessage(text: string): Promise<void> {
    this.assertConnected();
    this.send({
      type: "data",
      channel: "chat",
      payload: { text, from: this.config.kutanaAgentName },
    });
  }

  /**
   * Speak text aloud in the meeting via gateway TTS synthesis.
   * Sends the full start_speaking → spoken_text → stop_speaking sequence.
   * The gateway synthesizes the text using the configured TTS provider
   * and broadcasts the audio to all meeting participants.
   */
  async speak(text: string): Promise<void> {
    this.assertConnected();
    this.send({ type: "start_speaking" });
    this.send({ type: "spoken_text", text });
    this.send({ type: "stop_speaking" });
  }

  async acceptTask(taskId: string): Promise<void> {
    this.assertConnected();
    this.send({
      type: "data",
      channel: "task_updates",
      payload: { action: "accept", task_id: taskId, agent: "claude" },
    });
  }

  async updateTaskStatus(
    taskId: string,
    status: string,
    message: string,
  ): Promise<void> {
    this.assertConnected();
    this.send({
      type: "data",
      channel: "task_updates",
      payload: { action: "update_status", task_id: taskId, status, message },
    });
  }

  // ---------------------------------------------------------------------------
  // Public API — Turn management (requires active meeting)
  // ---------------------------------------------------------------------------

  async raiseHand(priority = "normal", topic?: string): Promise<void> {
    this.assertConnected();
    this.isInQueue = true;
    const msg: Record<string, unknown> = { type: "raise_hand", priority };
    if (topic) msg["topic"] = topic;
    this.send(msg);
  }

  async lowerHand(handRaiseId?: string): Promise<void> {
    this.assertConnected();
    this.isInQueue = false;
    const msg: Record<string, unknown> = { type: "lower_hand" };
    if (handRaiseId) msg["hand_raise_id"] = handRaiseId;
    this.send(msg);
  }

  async finishedSpeaking(): Promise<void> {
    this.assertConnected();
    this.isSpeaking = false;
    this.isInQueue = false;
    this.send({ type: "finished_speaking" });
  }

  /** Send get_queue; response arrives asynchronously as a turn.queue.updated event. */
  async requestQueueStatus(): Promise<void> {
    this.assertConnected();
    this.send({ type: "get_queue" });
  }

  getLastQueueStatus(): TurnQueueStatus | null {
    return this.lastQueueStatus;
  }

  getSpeakingStatus(): { isSpeaking: boolean; isInQueue: boolean } {
    return { isSpeaking: this.isSpeaking, isInQueue: this.isInQueue };
  }

  // ---------------------------------------------------------------------------
  // Public API — Buffer accessors
  // ---------------------------------------------------------------------------

  getRecentTranscript(limit = 50): TranscriptSegment[] {
    return this.transcriptBuffer.slice(-limit);
  }

  getEntities(entityType?: EntityType, limit = 50): AnyExtractedEntity[] {
    const all = entityType
      ? this.entityBuffer.filter((e) => e.entity_type === entityType)
      : this.entityBuffer;
    return all.slice(-limit);
  }

  getChatMessages(limit = 50): ChatMessage[] {
    return this.chatBuffer.slice(-limit);
  }

  /**
   * Return the current participant list, annotating our own session with
   * source: "claude-code".
   */
  getParticipants(): ParticipantInfo[] {
    const agentName = this.config.kutanaAgentName;
    return this.participantsBuffer.map((p) =>
      p.name === agentName ? { ...p, source: "claude-code" } : p,
    );
  }

  // ---------------------------------------------------------------------------
  // WebSocket lifecycle (private)
  // ---------------------------------------------------------------------------

  private connectWebSocket(
    meetingId: string,
    capabilities: string[],
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.token) {
        reject(new Error("Not authenticated — call authenticate() first"));
        return;
      }

      const wsUrl = `${this.config.kutanaApiUrl}/agent/connect?token=${this.token}`;
      const wsOptions = this.config.tlsRejectUnauthorized
        ? undefined
        : { rejectUnauthorized: false };
      this.ws = new this.WS(wsUrl, wsOptions);

      this.ws.on("open", () => {
        this.send({
          type: "join_meeting",
          meeting_id: meetingId,
          capabilities,
          tts_enabled: true,
        });
      });

      this.ws.on("message", (raw: Buffer) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(raw.toString()) as Record<string, unknown>;
        } catch {
          return;
        }

        if (msg["type"] === "joined") {
          const joined = msg as unknown as JoinedMessage;
          this.connected = true;
          this.currentMeetingId = meetingId;

          // Seed participant buffer from the joined message
          const initialParticipants = joined.participants ?? [];
          if (Array.isArray(initialParticipants)) {
            for (const p of initialParticipants as Array<
              Record<string, unknown>
            >) {
              this.upsertParticipant({
                participant_id: String(p["participant_id"] ?? p["id"] ?? ""),
                name: String(p["name"] ?? ""),
                role: String(p["role"] ?? "agent"),
                connection_type:
                  p["connection_type"] != null
                    ? String(p["connection_type"])
                    : null,
              });
            }
          }

          // Add our own session if not already present
          const selfName = this.config.kutanaAgentName;
          if (!this.participantsBuffer.find((p) => p.name === selfName)) {
            this.participantsBuffer.push({
              participant_id: "self",
              name: selfName,
              role: "agent",
              connection_type: "claude-code",
              source: "claude-code",
            });
          }

          // Subscribe to insight + chat data channels
          this.send({
            type: "subscribe_channel",
            channels: [
              "insights",
              "insights.task",
              "insights.decision",
              "insights.question",
              "insights.entity_mention",
              "insights.key_point",
              "insights.blocker",
              "insights.follow_up",
              "chat",
            ],
          });

          this.emit({
            topic: "meeting_lifecycle",
            type: "joined",
            content: `<meeting action="joined">Joined meeting ${String(joined.meeting_id)}.</meeting>`,
          });

          process.stderr.write(
            `[channel-server] Joined meeting ${String(joined.meeting_id)}\n`,
          );
          resolve();
        } else if (msg["type"] === "error" && !this.connected) {
          const err = msg as unknown as GatewayError;
          reject(new Error(`Join failed: ${err.message}`));
        } else {
          this.handleGatewayMessage(msg);
        }
      });

      this.ws.on("error", (err: Error) => {
        if (!this.connected) {
          reject(err);
        } else {
          process.stderr.write(
            `[channel-server] WebSocket error: ${err.message}\n`,
          );
        }
      });

      this.ws.on("close", () => {
        this.connected = false;
        process.stderr.write("[channel-server] Gateway connection closed\n");
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Message routing
  // ---------------------------------------------------------------------------

  private handleGatewayMessage(msg: Record<string, unknown>): void {
    const msgType = msg["type"] as string | undefined;

    if (msgType === "transcript" && this.shouldForwardTranscript()) {
      const segment = msg as unknown as TranscriptSegment;
      this.transcriptBuffer.push(segment);
      this.emit({
        topic: "transcript",
        type: "transcript_segment",
        content: formatTranscript(segment),
      });
    } else if (msgType === "event") {
      this.handleEventMessage(msg as unknown as GatewayEvent);
    } else if (msgType === "participant_update") {
      this.handleParticipantUpdate(msg);
    }
  }

  private handleEventMessage(event: GatewayEvent): void {
    const et = event.event_type ?? "";

    // Insight channels
    if (
      et.startsWith("data.channel.insights") &&
      this.shouldForwardInsights()
    ) {
      const payload = event.payload as InsightPayload | undefined;
      if (payload?.entities) {
        const filtered = this.applyEntityFilter(payload.entities);
        for (const entity of filtered) {
          this.entityBuffer.push(entity);
          this.emit({
            topic: "insight",
            type: entity.entity_type,
            content: formatEntity(entity),
          });
        }
      }
      return;
    }

    // Chat channel — agent data channel messages (via EventRelay)
    // AND chat.message.received events (via ChatBridge, e.g. from browser users)
    if (et === "data.channel.chat" || et === "chat.message.received") {
      const p = event.payload as Record<string, unknown> | undefined;
      if (p) {
        const msg: ChatMessage = {
          index: this.chatIndex++,
          sender_name: String(p["sender_name"] ?? p["from"] ?? "Unknown"),
          sender_session_id: String(p["sender_session_id"] ?? p["sender_id"] ?? ""),
          text: String(
            p["content"] ?? (
              p["payload"] != null
                ? ((p["payload"] as Record<string, unknown>)["text"] ?? "")
                : (p["text"] ?? "")
            ),
          ),
          timestamp: String(p["sent_at"] ?? new Date().toISOString()),
        };
        this.chatBuffer.push(msg);
        this.emit({
          topic: "chat",
          type: "chat_message",
          content: formatChatMessage(msg),
        });
      }
      return;
    }

    // Turn management events
    if (et === "turn.queue.updated") {
      const p = event.payload as Record<string, unknown> | undefined;
      if (p) {
        this.lastQueueStatus = {
          meeting_id: String(p["meeting_id"] ?? ""),
          active_speaker_id:
            p["active_speaker_id"] != null
              ? String(p["active_speaker_id"])
              : null,
          queue: Array.isArray(p["queue"])
            ? (p["queue"] as Array<Record<string, unknown>>).map((entry) => ({
                position: Number(entry["position"] ?? 0),
                participant_id: String(entry["participant_id"] ?? ""),
                priority: String(entry["priority"] ?? "normal"),
                topic:
                  entry["topic"] != null ? String(entry["topic"]) : null,
                raised_at: String(entry["raised_at"] ?? ""),
                hand_raise_id:
                  entry["hand_raise_id"] != null
                    ? String(entry["hand_raise_id"])
                    : undefined,
              }))
            : [],
        };
        this.emit({
          topic: "turn",
          type: "queue_updated",
          content: formatQueueStatus(this.lastQueueStatus!),
        });
      }
      return;
    }

    if (et === "turn.speaker.changed") {
      const p = event.payload as Record<string, unknown> | undefined;
      if (p) {
        this.emit({
          topic: "turn",
          type: "speaker_changed",
          content: formatSpeakerChanged(p),
        });
      }
      return;
    }

    if (et === "turn.your_turn") {
      this.isSpeaking = true;
      this.isInQueue = false;
      this.emit({
        topic: "turn",
        type: "your_turn",
        content:
          "<turn>It's your turn to speak. Use mark_finished_speaking when done.</turn>",
      });
      return;
    }

    if (et === "turn.hand.raised") {
      const p = event.payload as Record<string, unknown> | undefined;
      if (p) {
        this.emit({
          topic: "turn",
          type: "hand_raised",
          content: `<turn>Hand raised: participant ${String(p["participant_id"] ?? "")} at queue position ${String(p["queue_position"] ?? "")}</turn>`,
        });
      }
      return;
    }

    if (et === "turn.speaker.finished") {
      const p = event.payload as Record<string, unknown> | undefined;
      if (p) {
        this.emit({
          topic: "turn",
          type: "speaker_finished",
          content: `<turn>Speaker ${String(p["participant_id"] ?? "")} finished their turn.</turn>`,
        });
      }
    }
  }

  private handleParticipantUpdate(msg: Record<string, unknown>): void {
    const action = String(msg["action"] ?? "");
    const pid = String(msg["participant_id"] ?? "");
    const name = String(msg["name"] ?? "");
    const role = String(msg["role"] ?? "agent");
    const connectionType =
      msg["connection_type"] != null ? String(msg["connection_type"]) : null;

    if (action === "joined") {
      this.upsertParticipant({
        participant_id: pid,
        name,
        role,
        connection_type: connectionType,
      });
      this.emit({
        topic: "participant",
        type: "joined",
        content: `<participant action="joined">${name} (${role}) joined the meeting.</participant>`,
      });
    } else if (action === "left") {
      this.participantsBuffer = this.participantsBuffer.filter(
        (p) => p.participant_id !== pid,
      );
      this.emit({
        topic: "participant",
        type: "left",
        content: `<participant action="left">${name} left the meeting.</participant>`,
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Mode filtering
  // ---------------------------------------------------------------------------

  private shouldForwardTranscript(): boolean {
    return (
      this.config.agentMode === "transcript" ||
      this.config.agentMode === "both"
    );
  }

  private shouldForwardInsights(): boolean {
    return (
      this.config.agentMode === "insights" ||
      this.config.agentMode === "both" ||
      this.config.agentMode === "selective"
    );
  }

  private applyEntityFilter(
    entities: AnyExtractedEntity[],
  ): AnyExtractedEntity[] {
    if (
      this.config.agentMode !== "selective" ||
      this.config.entityFilter.length === 0
    ) {
      return entities;
    }
    return entities.filter((e) =>
      (this.config.entityFilter as string[]).includes(e.entity_type),
    );
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  private resetBuffers(): void {
    this.transcriptBuffer = [];
    this.entityBuffer = [];
    this.chatBuffer = [];
    this.participantsBuffer = [];
    this.lastQueueStatus = null;
    this.isSpeaking = false;
    this.isInQueue = false;
    this.chatIndex = 0;
  }

  private upsertParticipant(p: ParticipantInfo): void {
    const idx = this.participantsBuffer.findIndex(
      (x) => x.participant_id === p.participant_id,
    );
    if (idx >= 0) {
      this.participantsBuffer[idx] = p;
    } else {
      this.participantsBuffer.push(p);
    }
  }

  private send(payload: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  private emit(msg: ChannelMessage): void {
    if (this.channelCallback) {
      const result = this.channelCallback(msg);
      if (result instanceof Promise) {
        result.catch((err: unknown) => {
          process.stderr.write(
            `[channel-server] Channel callback error: ${String(err)}\n`,
          );
        });
      }
    }
  }

  private assertConnected(): void {
    if (!this.connected || !this.currentMeetingId) {
      throw new Error(
        "Not in a meeting. Use join_meeting first.",
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatTranscript(segment: TranscriptSegment): string {
  const speaker = segment.speaker ?? "Unknown";
  const start = segment.start_time.toFixed(1);
  const end = segment.end_time.toFixed(1);
  return `<transcript>[${start}s-${end}s] ${speaker}: ${segment.text}</transcript>`;
}

function formatEntity(entity: AnyExtractedEntity): string {
  return `<insight type="${entity.entity_type}">${JSON.stringify(entity, null, 2)}</insight>`;
}

function formatChatMessage(msg: ChatMessage): string {
  return `<chat>[${msg.timestamp}] ${msg.sender_name}: ${msg.text}</chat>`;
}

function formatQueueStatus(status: TurnQueueStatus): string {
  const speaker = status.active_speaker_id ?? "none";
  const queueStr =
    status.queue.length === 0
      ? "Queue is empty."
      : status.queue
          .map(
            (e) =>
              `  ${e.position.toString()}. ${e.participant_id}${e.topic ? ` — "${e.topic}"` : ""}`,
          )
          .join("\n");
  return `<turn type="queue_updated">Active speaker: ${speaker}\n${queueStr}</turn>`;
}

function formatSpeakerChanged(p: Record<string, unknown>): string {
  const prev =
    p["previous_speaker_id"] != null
      ? String(p["previous_speaker_id"])
      : "none";
  const next =
    p["new_speaker_id"] != null ? String(p["new_speaker_id"]) : "none";
  return `<turn type="speaker_changed">Speaker changed: ${prev} → ${next}</turn>`;
}
