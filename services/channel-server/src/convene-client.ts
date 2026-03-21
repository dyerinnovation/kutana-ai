/**
 * Convene AI WebSocket client for the channel server.
 *
 * Authenticates with the Convene API server to exchange an agent API key for
 * a gateway JWT, then connects to the agent gateway WebSocket, joins the
 * configured meeting, and forwards incoming events to registered callbacks.
 *
 * Supports the four agent modes (transcript, insights, both, selective) by
 * filtering events before forwarding.
 */

import WebSocket from "ws";
import type { ChannelServerConfig } from "./config.js";
import type {
  AnyExtractedEntity,
  ChannelMessage,
  EntityType,
  GatewayError,
  GatewayEvent,
  InsightPayload,
  JoinedMessage,
  TranscriptSegment,
} from "./types.js";

/** Callback invoked when a channel-worthy event arrives. */
export type ChannelEventCallback = (
  message: ChannelMessage,
) => Promise<void> | void;

/** Injectable WebSocket constructor — allows test code to supply a mock. */
export type WebSocketConstructor = new (url: string) => WebSocket;

export class ConveneClient {
  private ws: WebSocket | null = null;
  private token: string | null = null;
  private connected = false;
  private channelCallback: ChannelEventCallback | null = null;

  private transcriptBuffer: TranscriptSegment[] = [];
  private entityBuffer: AnyExtractedEntity[] = [];

  constructor(
    private readonly config: ChannelServerConfig,
    /** Allows injecting a mock WebSocket in tests. */
    private readonly WS: WebSocketConstructor = WebSocket,
  ) {}

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /** Register a callback that receives channel messages. */
  onChannelMessage(callback: ChannelEventCallback): void {
    this.channelCallback = callback;
  }

  /** Authenticate and connect to the Convene agent gateway. */
  async connect(): Promise<void> {
    await this.authenticate();
    await this.connectWebSocket();
  }

  /** Disconnect gracefully from the gateway. */
  async disconnect(): Promise<void> {
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
  }

  isConnected(): boolean {
    return this.connected;
  }

  // ---------------------------------------------------------------------------
  // Two-way communication (called by MCP tool handlers)
  // ---------------------------------------------------------------------------

  async sendChatMessage(text: string): Promise<void> {
    this.assertConnected();
    this.send({
      type: "data",
      channel: "chat",
      payload: { text, from: "agent" },
    });
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
  // Buffer accessors (called by MCP tool handlers)
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

  // ---------------------------------------------------------------------------
  // Authentication
  // ---------------------------------------------------------------------------

  private async authenticate(): Promise<void> {
    const url = `${this.config.conveneHttpUrl}/api/v1/token/gateway`;
    const resp = await fetch(url, {
      method: "POST",
      headers: { "X-API-Key": this.config.conveneApiKey },
    });

    if (!resp.ok) {
      throw new Error(
        `Convene auth failed: ${resp.status.toString()} ${resp.statusText}`,
      );
    }

    const data = (await resp.json()) as { token: string };
    this.token = data.token;
  }

  // ---------------------------------------------------------------------------
  // WebSocket lifecycle
  // ---------------------------------------------------------------------------

  private connectWebSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.token) {
        reject(new Error("Not authenticated — call authenticate() first"));
        return;
      }

      const wsUrl = `${this.config.conveneApiUrl}/agent/connect?token=${this.token}`;
      this.ws = new this.WS(wsUrl);

      this.ws.on("open", () => {
        this.send({
          type: "join_meeting",
          meeting_id: this.config.conveneMeetingId,
          capabilities: ["listen", "transcribe", "data_channel"],
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
          // Subscribe to insight data channels
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
          process.stderr.write(
            `[channel-server] Joined meeting ${joined.meeting_id}\n`,
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
          process.stderr.write(`[channel-server] WebSocket error: ${err.message}\n`);
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
    }
  }

  private handleEventMessage(event: GatewayEvent): void {
    const isInsightChannel =
      event.event_type?.startsWith("data.channel.insights") ?? false;

    if (isInsightChannel && this.shouldForwardInsights()) {
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
    if (!this.connected) {
      throw new Error(
        "ConveneClient is not connected to a meeting. Call connect() first.",
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
