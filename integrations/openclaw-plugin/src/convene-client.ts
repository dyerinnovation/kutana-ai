/**
 * HTTP client for communicating with the Convene MCP server or API.
 */

export interface ConveneConfig {
  apiKey: string;
  mcpUrl: string;
}

export interface Meeting {
  id: string;
  title: string;
  platform: string;
  status: string;
  scheduled_at: string;
  created_at: string;
}

export interface TranscriptSegment {
  speaker_id: string | null;
  text: string;
  start_time: number;
  end_time: number;
  confidence: number;
  is_final: boolean;
}

export interface Task {
  id: string;
  meeting_id: string;
  description: string;
  priority: string;
  status: string;
  created_at: string;
}

export interface Participant {
  id: string;
  name: string;
  role: string;
  connection_type: string;
  source?: string;
}

export interface TurnQueueStatus {
  meeting_id: string | null;
  active_speaker_id: string | null;
  queue: Array<{
    position: number;
    participant_id: string;
    priority: string;
    topic: string | null;
  }>;
  your_position: number | null;
  total_in_queue: number;
}

export interface ChatMessage {
  id?: string;
  sender_name?: string;
  sender_id?: string;
  text: string;
  sent_at?: string;
}

export class ConveneClient {
  private bearerToken: string | null = null;

  constructor(private config: ConveneConfig) {}

  /**
   * Exchange API key for MCP Bearer token.
   */
  async authenticate(): Promise<void> {
    const apiBaseUrl = this.config.mcpUrl.replace("/mcp", "").replace(":3001", ":8000");
    const resp = await fetch(`${apiBaseUrl}/api/v1/token/mcp`, {
      method: "POST",
      headers: {
        "X-API-Key": this.config.apiKey,
      },
    });

    if (!resp.ok) {
      throw new Error(`Authentication failed: ${resp.status} ${resp.statusText}`);
    }

    const data = (await resp.json()) as { token: string };
    this.bearerToken = data.token;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.bearerToken) {
      headers["Authorization"] = `Bearer ${this.bearerToken}`;
    }
    return headers;
  }

  private async callTool(name: string, args: Record<string, unknown>): Promise<string> {
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: { name, arguments: args },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    return result.result?.content?.[0]?.text ?? "";
  }

  async listMeetings(): Promise<Meeting[]> {
    const text = await this.callTool("list_meetings", {});
    try { return JSON.parse(text) as Meeting[]; } catch { return []; }
  }

  async joinMeeting(meetingId: string): Promise<string> {
    return this.callTool("join_meeting", { meeting_id: meetingId });
  }

  async getTranscript(lastN: number = 50): Promise<TranscriptSegment[]> {
    const text = await this.callTool("get_transcript", { last_n: lastN });
    try { return JSON.parse(text) as TranscriptSegment[]; } catch { return []; }
  }

  async createTask(meetingId: string, description: string, priority: string = "medium"): Promise<Task> {
    const text = await this.callTool("create_task", { meeting_id: meetingId, description, priority });
    return JSON.parse(text) as Task;
  }

  async getParticipants(): Promise<Participant[]> {
    const text = await this.callTool("get_participants", {});
    try { return JSON.parse(text) as Participant[]; } catch { return []; }
  }

  async createMeeting(title: string): Promise<Meeting> {
    const text = await this.callTool("create_new_meeting", { title, platform: "convene" });
    return JSON.parse(text) as Meeting;
  }

  // ---------------------------------------------------------------------------
  // Turn management
  // ---------------------------------------------------------------------------

  async raiseHand(priority: string = "normal", topic?: string): Promise<string> {
    const args: Record<string, unknown> = { priority };
    if (topic) args["topic"] = topic;
    return this.callTool("raise_hand", args);
  }

  async getQueueStatus(meetingId: string): Promise<TurnQueueStatus> {
    const text = await this.callTool("get_queue_status", { meeting_id: meetingId });
    return JSON.parse(text) as TurnQueueStatus;
  }

  async markFinishedSpeaking(meetingId: string): Promise<string> {
    return this.callTool("mark_finished_speaking", { meeting_id: meetingId });
  }

  async cancelHandRaise(meetingId: string, handRaiseId?: string): Promise<string> {
    const args: Record<string, unknown> = { meeting_id: meetingId };
    if (handRaiseId) args["hand_raise_id"] = handRaiseId;
    return this.callTool("cancel_hand_raise", args);
  }

  async getSpeakingStatus(meetingId: string): Promise<string> {
    return this.callTool("get_speaking_status", { meeting_id: meetingId });
  }

  // ---------------------------------------------------------------------------
  // Chat
  // ---------------------------------------------------------------------------

  async sendChatMessage(meetingId: string, text: string): Promise<string> {
    return this.callTool("send_chat_message", { meeting_id: meetingId, text });
  }

  async getChatMessages(meetingId: string, limit: number = 50): Promise<ChatMessage[]> {
    const result = await this.callTool("get_chat_messages", { meeting_id: meetingId, limit });
    try { return JSON.parse(result) as ChatMessage[]; } catch { return []; }
  }
}
