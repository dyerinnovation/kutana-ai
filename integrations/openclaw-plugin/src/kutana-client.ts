/**
 * HTTP client for communicating with the Kutana MCP server or API.
 */

export interface KutanaConfig {
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
}

export class KutanaClient {
  private bearerToken: string | null = null;

  constructor(private config: KutanaConfig) {}

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

  async listMeetings(): Promise<Meeting[]> {
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: { name: "list_meetings", arguments: {} },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    if (result.result?.content?.[0]?.text) {
      return JSON.parse(result.result.content[0].text) as Meeting[];
    }
    return [];
  }

  async joinMeeting(meetingId: string, capabilities?: string[]): Promise<string> {
    const args: Record<string, unknown> = { meeting_id: meetingId };
    if (capabilities && capabilities.length > 0) {
      args["capabilities"] = capabilities;
    }
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: { name: "join_meeting", arguments: args },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    return result.result?.content?.[0]?.text ?? "Failed to join meeting";
  }

  async getTranscript(lastN: number = 50): Promise<TranscriptSegment[]> {
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: { name: "get_transcript", arguments: { last_n: lastN } },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    if (result.result?.content?.[0]?.text) {
      return JSON.parse(result.result.content[0].text) as TranscriptSegment[];
    }
    return [];
  }

  async createTask(
    meetingId: string,
    description: string,
    priority: string = "medium"
  ): Promise<Task> {
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: {
          name: "create_task",
          arguments: {
            meeting_id: meetingId,
            description,
            priority,
          },
        },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    if (result.result?.content?.[0]?.text) {
      return JSON.parse(result.result.content[0].text) as Task;
    }
    throw new Error("Failed to create task");
  }

  async getParticipants(): Promise<Participant[]> {
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: { name: "get_participants", arguments: {} },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    if (result.result?.content?.[0]?.text) {
      return JSON.parse(result.result.content[0].text) as Participant[];
    }
    return [];
  }

  async createMeeting(title: string): Promise<Meeting> {
    const resp = await fetch(`${this.config.mcpUrl}`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: {
          name: "create_meeting",
          arguments: { title, platform: "kutana" },
        },
        id: 1,
      }),
    });

    const result = (await resp.json()) as { result?: { content: Array<{ text: string }> } };
    if (result.result?.content?.[0]?.text) {
      return JSON.parse(result.result.content[0].text) as Meeting;
    }
    throw new Error("Failed to create meeting");
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
    return result.result?.content?.[0]?.text ?? JSON.stringify({ error: `Tool ${name} returned no result` });
  }

  // Turn Management

  async startSpeaking(meetingId: string): Promise<string> {
    return this.callTool("start_speaking", { meeting_id: meetingId });
  }

  async raiseHand(meetingId: string, priority: string = "normal", topic?: string): Promise<string> {
    return this.callTool("raise_hand", { meeting_id: meetingId, priority, ...(topic ? { topic } : {}) });
  }

  async getQueueStatus(meetingId: string): Promise<string> {
    return this.callTool("get_queue_status", { meeting_id: meetingId });
  }

  async markFinishedSpeaking(meetingId: string): Promise<string> {
    return this.callTool("mark_finished_speaking", { meeting_id: meetingId });
  }

  async cancelHandRaise(meetingId: string, handRaiseId?: string): Promise<string> {
    return this.callTool("cancel_hand_raise", { meeting_id: meetingId, ...(handRaiseId ? { hand_raise_id: handRaiseId } : {}) });
  }

  // Chat

  async sendChatMessage(meetingId: string, content: string, messageType: string = "text"): Promise<string> {
    return this.callTool("send_chat_message", { meeting_id: meetingId, content, message_type: messageType });
  }

  async getChatMessages(meetingId: string, limit: number = 50, messageType?: string): Promise<string> {
    return this.callTool("get_chat_messages", { meeting_id: meetingId, limit, ...(messageType ? { message_type: messageType } : {}) });
  }
}
