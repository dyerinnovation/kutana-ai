/**
 * Tests for MCP tool schemas and handlers.
 *
 * Tools are tested by constructing a mock KutanaClient and calling the tool
 * handlers through a real Server instance. This exercises the routing logic
 * without any network I/O.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { registerTools } from "../src/tools.js";
import type { KutanaClient } from "../src/kutana-client.js";
import type { TaskEntity, DecisionEntity, QuestionEntity, ChatMessage, ParticipantInfo, TurnQueueStatus } from "../src/types.js";

// Helper to retrieve an internal request handler from the MCP Server.
// The SDK stores handlers in the private `_requestHandlers` Map.
function getHandler(server: Server, methodName: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access
  return (server as any)._requestHandlers.get(methodName) as
    | ((req: Record<string, unknown>, extra: unknown) => Promise<unknown>)
    | undefined;
}

// ---------------------------------------------------------------------------
// Mock client factory
// ---------------------------------------------------------------------------

function makeMockClient(overrides: Partial<KutanaClient> = {}): KutanaClient {
  return {
    onChannelMessage: vi.fn(),
    authenticate: vi.fn(),
    joinMeeting: vi.fn(),
    leaveMeeting: vi.fn(),
    listMeetings: vi.fn(async () => []),
    createMeeting: vi.fn(),
    isConnected: vi.fn(() => true),
    getCurrentMeetingId: vi.fn(() => "meeting-123"),
    sendChatMessage: vi.fn(),
    acceptTask: vi.fn(),
    updateTaskStatus: vi.fn(),
    getRecentTranscript: vi.fn(() => []),
    getEntities: vi.fn(() => []),
    getChatMessages: vi.fn(() => []),
    getParticipants: vi.fn(() => []),
    raiseHand: vi.fn(),
    lowerHand: vi.fn(),
    finishedSpeaking: vi.fn(),
    requestQueueStatus: vi.fn(),
    getLastQueueStatus: vi.fn(() => null),
    getSpeakingStatus: vi.fn(() => ({ isSpeaking: false, isInQueue: false })),
    ...overrides,
  } as unknown as KutanaClient;
}

function makeServer(client: KutanaClient): Server {
  const server = new Server(
    { name: "test", version: "0.0.0" },
    { capabilities: { tools: {} } },
  );
  registerTools(server, client);
  return server;
}

// ---------------------------------------------------------------------------
// Tool listing
// ---------------------------------------------------------------------------

describe("list tools", () => {
  it("returns all eighteen tool names", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, ListToolsRequestSchema.shape.method.value);
    expect(handler).toBeDefined();

    const result = await handler!({ method: "tools/list", params: {} }, {});
    const tools = (result as { tools: Array<{ name: string }> }).tools;
    const names = tools.map((t) => t.name);

    // Chat / messaging
    expect(names).toContain("reply");
    expect(names).toContain("get_chat_messages");
    // Task
    expect(names).toContain("accept_task");
    expect(names).toContain("update_status");
    // Turn management
    expect(names).toContain("raise_hand");
    expect(names).toContain("get_queue_status");
    expect(names).toContain("mark_finished_speaking");
    expect(names).toContain("cancel_hand_raise");
    expect(names).toContain("get_speaking_status");
    // Participants
    expect(names).toContain("get_participants");
    // Transcript / entities
    expect(names).toContain("request_context");
    expect(names).toContain("get_meeting_recap");
    expect(names).toContain("get_entity_history");
    expect(names).toHaveLength(18);
  });

  it("reply tool has required text property in schema", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, ListToolsRequestSchema.shape.method.value);
    const result = await handler!({ method: "tools/list", params: {} }, {});
    const tools = (result as { tools: Array<{ name: string; inputSchema: Record<string, unknown> }> }).tools;
    const reply = tools.find((t) => t.name === "reply");
    expect(reply?.inputSchema["required"]).toContain("text");
  });

  it("raise_hand tool has optional priority enum", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, ListToolsRequestSchema.shape.method.value);
    const result = await handler!({ method: "tools/list", params: {} }, {});
    const tools = (result as { tools: Array<{ name: string; inputSchema: { properties: Record<string, { enum?: string[] }> } }> }).tools;
    const tool = tools.find((t) => t.name === "raise_hand");
    expect(tool?.inputSchema.properties["priority"]?.enum).toContain("normal");
    expect(tool?.inputSchema.properties["priority"]?.enum).toContain("urgent");
  });

  it("get_entity_history has entity_type enum with all 7 types", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, ListToolsRequestSchema.shape.method.value);
    const result = await handler!({ method: "tools/list", params: {} }, {});
    const tools = (result as { tools: Array<{ name: string; inputSchema: { properties: Record<string, { enum?: string[] }> } }> }).tools;
    const tool = tools.find((t) => t.name === "get_entity_history");
    const enumValues = tool?.inputSchema.properties["entity_type"]?.enum ?? [];
    expect(enumValues).toContain("task");
    expect(enumValues).toContain("decision");
    expect(enumValues).toContain("follow_up");
    expect(enumValues).toHaveLength(7);
  });
});

// ---------------------------------------------------------------------------
// reply tool
// ---------------------------------------------------------------------------

describe("reply tool", () => {
  it("calls sendChatMessage with the provided text", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      { method: "tools/call", params: { name: "reply", arguments: { text: "Hello meeting!" } } },
      {},
    );

    expect(client.sendChatMessage).toHaveBeenCalledWith("Hello meeting!");
  });

  it("returns error when text is missing", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "reply", arguments: {} } },
      {},
    );

    const res = result as { isError?: boolean; content: Array<{ text: string }> };
    expect(res.isError).toBe(true);
    expect(res.content[0]?.text).toMatch(/text is required/i);
    expect(client.sendChatMessage).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// get_chat_messages tool
// ---------------------------------------------------------------------------

describe("get_chat_messages tool", () => {
  it("returns chat messages from the buffer", async () => {
    const msgs: ChatMessage[] = [
      { index: 0, sender_name: "Alice", sender_session_id: "s1", text: "Hi there", timestamp: "2026-03-23T10:00:00Z" },
      { index: 1, sender_name: "Bob", sender_session_id: "s2", text: "Hello!", timestamp: "2026-03-23T10:00:05Z" },
    ];
    const client = makeMockClient({ getChatMessages: vi.fn(() => msgs) });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_chat_messages", arguments: { limit: 10 } } },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    const parsed = JSON.parse(res.content[0]?.text ?? "[]") as ChatMessage[];
    expect(parsed).toHaveLength(2);
    expect(client.getChatMessages).toHaveBeenCalledWith(10);
  });

  it("uses default limit of 50 when not provided", async () => {
    const client = makeMockClient({ getChatMessages: vi.fn(() => []) });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      { method: "tools/call", params: { name: "get_chat_messages", arguments: {} } },
      {},
    );

    expect(client.getChatMessages).toHaveBeenCalledWith(50);
  });
});

// ---------------------------------------------------------------------------
// accept_task tool
// ---------------------------------------------------------------------------

describe("accept_task tool", () => {
  it("calls acceptTask with the task_id", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      {
        method: "tools/call",
        params: { name: "accept_task", arguments: { task_id: "task-abc" } },
      },
      {},
    );

    expect(client.acceptTask).toHaveBeenCalledWith("task-abc");
  });

  it("returns error when task_id is missing", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "accept_task", arguments: {} } },
      {},
    );

    const res = result as { isError?: boolean };
    expect(res.isError).toBe(true);
    expect(client.acceptTask).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// update_status tool
// ---------------------------------------------------------------------------

describe("update_status tool", () => {
  it("calls updateTaskStatus with all three params", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      {
        method: "tools/call",
        params: {
          name: "update_status",
          arguments: {
            task_id: "task-1",
            status: "in_progress",
            message: "Working on it",
          },
        },
      },
      {},
    );

    expect(client.updateTaskStatus).toHaveBeenCalledWith(
      "task-1",
      "in_progress",
      "Working on it",
    );
  });

  it("returns error when any param is missing", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      {
        method: "tools/call",
        params: { name: "update_status", arguments: { task_id: "t1" } },
      },
      {},
    );

    const res = result as { isError?: boolean };
    expect(res.isError).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Turn management tools
// ---------------------------------------------------------------------------

describe("raise_hand tool", () => {
  it("calls raiseHand with default normal priority", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      { method: "tools/call", params: { name: "raise_hand", arguments: {} } },
      {},
    );

    expect(client.raiseHand).toHaveBeenCalledWith("normal", undefined);
  });

  it("calls raiseHand with urgent priority and topic", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      {
        method: "tools/call",
        params: { name: "raise_hand", arguments: { priority: "urgent", topic: "blocking issue" } },
      },
      {},
    );

    expect(client.raiseHand).toHaveBeenCalledWith("urgent", "blocking issue");
  });
});

describe("get_queue_status tool", () => {
  it("calls requestQueueStatus and returns cached state", async () => {
    const queueStatus: TurnQueueStatus = {
      meeting_id: "m1",
      active_speaker_id: "p1",
      queue: [{ position: 1, participant_id: "p2", priority: "normal", topic: null, raised_at: "2026-03-23T10:00:00Z" }],
    };
    const client = makeMockClient({
      getLastQueueStatus: vi.fn(() => queueStatus),
    });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_queue_status", arguments: {} } },
      {},
    );

    expect(client.requestQueueStatus).toHaveBeenCalled();
    const res = result as { content: Array<{ text: string }> };
    const parsed = JSON.parse(res.content[0]?.text ?? "{}") as TurnQueueStatus;
    expect(parsed.active_speaker_id).toBe("p1");
    expect(parsed.queue).toHaveLength(1);
  });

  it("returns note when no cached state", async () => {
    const client = makeMockClient({ getLastQueueStatus: vi.fn(() => null) });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_queue_status", arguments: {} } },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    expect(res.content[0]?.text).toMatch(/no cached state/i);
  });
});

describe("mark_finished_speaking tool", () => {
  it("calls finishedSpeaking", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      { method: "tools/call", params: { name: "mark_finished_speaking", arguments: {} } },
      {},
    );

    expect(client.finishedSpeaking).toHaveBeenCalled();
  });
});

describe("cancel_hand_raise tool", () => {
  it("calls lowerHand with no hand_raise_id by default", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      { method: "tools/call", params: { name: "cancel_hand_raise", arguments: {} } },
      {},
    );

    expect(client.lowerHand).toHaveBeenCalledWith(undefined);
  });

  it("passes hand_raise_id to lowerHand when provided", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    await handler!(
      {
        method: "tools/call",
        params: { name: "cancel_hand_raise", arguments: { hand_raise_id: "hr-123" } },
      },
      {},
    );

    expect(client.lowerHand).toHaveBeenCalledWith("hr-123");
  });
});

describe("get_speaking_status tool", () => {
  it("returns is_speaking and is_in_queue from local tracking", async () => {
    const client = makeMockClient({
      getSpeakingStatus: vi.fn(() => ({ isSpeaking: true, isInQueue: false })),
      getLastQueueStatus: vi.fn(() => null),
    });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_speaking_status", arguments: {} } },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    const parsed = JSON.parse(res.content[0]?.text ?? "{}") as { is_speaking: boolean; is_in_queue: boolean };
    expect(parsed.is_speaking).toBe(true);
    expect(parsed.is_in_queue).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// get_participants tool
// ---------------------------------------------------------------------------

describe("get_participants tool", () => {
  it("returns participant list including claude-code source", async () => {
    const participants: ParticipantInfo[] = [
      { participant_id: "p1", name: "Alice", role: "human", connection_type: "webrtc" },
      { participant_id: "self", name: "Claude Code", role: "agent", connection_type: "claude-code", source: "claude-code" },
    ];
    const client = makeMockClient({ getParticipants: vi.fn(() => participants) });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_participants", arguments: {} } },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    const parsed = JSON.parse(res.content[0]?.text ?? "[]") as ParticipantInfo[];
    expect(parsed).toHaveLength(2);
    const self = parsed.find((p) => p.name === "Claude Code");
    expect(self?.source).toBe("claude-code");
  });
});

// ---------------------------------------------------------------------------
// request_context tool
// ---------------------------------------------------------------------------

describe("request_context tool", () => {
  it("filters transcript by query keyword", async () => {
    const segments = [
      { type: "transcript", meeting_id: "m1", segment_id: "s1", speaker: "Alice",
        text: "Deploy the auth fix", start_time: 1, end_time: 2, confidence: 0.9, is_final: true },
      { type: "transcript", meeting_id: "m1", segment_id: "s2", speaker: "Bob",
        text: "Discuss the timeline", start_time: 3, end_time: 4, confidence: 0.9, is_final: true },
    ] as const;

    const client = makeMockClient({
      getRecentTranscript: vi.fn(() => [...segments]),
    });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "request_context", arguments: { query: "auth" } } },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    const parsed = JSON.parse(res.content[0]?.text ?? "[]") as unknown[];
    expect(parsed).toHaveLength(1);
    const first = parsed[0] as { text: string };
    expect(first.text).toContain("auth");
  });

  it("returns error when query is missing", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "request_context", arguments: {} } },
      {},
    );
    const res = result as { isError?: boolean };
    expect(res.isError).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// get_meeting_recap tool
// ---------------------------------------------------------------------------

describe("get_meeting_recap tool", () => {
  it("builds recap from entity buffer", async () => {
    const task: TaskEntity = {
      id: "t1", entity_type: "task", meeting_id: "m1", confidence: 0.9,
      extracted_at: new Date().toISOString(), batch_id: "b1",
      title: "Fix auth", assignee: "Alice", deadline: null,
      priority: "high", status: "identified", source_speaker: null, source_segment_id: null,
    };
    const decision: DecisionEntity = {
      id: "d1", entity_type: "decision", meeting_id: "m1", confidence: 0.85,
      extracted_at: new Date().toISOString(), batch_id: "b1",
      summary: "Use Redis for sessions", participants: ["Alice", "Bob"],
      rationale: "Better performance", source_segment_ids: [],
    };
    const question: QuestionEntity = {
      id: "q1", entity_type: "question", meeting_id: "m1", confidence: 0.8,
      extracted_at: new Date().toISOString(), batch_id: "b1",
      text: "What's the deadline?", asker: "Bob", status: "open",
      answer: null, source_segment_id: null,
    };

    const client = makeMockClient({
      getEntities: vi.fn((entityType?: string) => {
        if (!entityType) return [task, decision, question];
        if (entityType === "task") return [task];
        if (entityType === "decision") return [decision];
        if (entityType === "question") return [question];
        return [];
      }),
    });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_meeting_recap", arguments: {} } },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    const recap = JSON.parse(res.content[0]?.text ?? "{}") as {
      tasks: unknown[];
      decisions: unknown[];
      open_questions: unknown[];
    };

    expect(recap.tasks).toHaveLength(1);
    expect(recap.decisions).toHaveLength(1);
    expect(recap.open_questions).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// get_entity_history tool
// ---------------------------------------------------------------------------

describe("get_entity_history tool", () => {
  it("returns entities of the requested type", async () => {
    const task: TaskEntity = {
      id: "t1", entity_type: "task", meeting_id: "m1", confidence: 0.9,
      extracted_at: new Date().toISOString(), batch_id: "b1",
      title: "Fix auth", assignee: null, deadline: null,
      priority: "medium", status: "identified", source_speaker: null, source_segment_id: null,
    };
    const client = makeMockClient({
      getEntities: vi.fn(() => [task]),
    });
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      {
        method: "tools/call",
        params: { name: "get_entity_history", arguments: { entity_type: "task", limit: 10 } },
      },
      {},
    );

    const res = result as { content: Array<{ text: string }> };
    const entities = JSON.parse(res.content[0]?.text ?? "[]") as unknown[];
    expect(entities).toHaveLength(1);
    expect(client.getEntities).toHaveBeenCalledWith("task", 10);
  });

  it("returns error when entity_type is missing", async () => {
    const client = makeMockClient();
    const server = makeServer(client);
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "get_entity_history", arguments: {} } },
      {},
    );
    const res = result as { isError?: boolean };
    expect(res.isError).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// unknown tool
// ---------------------------------------------------------------------------

describe("unknown tool", () => {
  it("returns isError for unknown tool name", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, CallToolRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "tools/call", params: { name: "nonexistent", arguments: {} } },
      {},
    );
    const res = result as { isError?: boolean };
    expect(res.isError).toBe(true);
  });
});
