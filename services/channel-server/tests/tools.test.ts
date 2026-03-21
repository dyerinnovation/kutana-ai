/**
 * Tests for MCP tool schemas and handlers.
 *
 * Tools are tested by constructing a mock ConveneClient and calling the tool
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
import type { ConveneClient } from "../src/convene-client.js";
import type { TaskEntity, DecisionEntity, QuestionEntity } from "../src/types.js";

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

function makeMockClient(overrides: Partial<ConveneClient> = {}): ConveneClient {
  return {
    onChannelMessage: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    isConnected: vi.fn(() => true),
    sendChatMessage: vi.fn(),
    acceptTask: vi.fn(),
    updateTaskStatus: vi.fn(),
    getRecentTranscript: vi.fn(() => []),
    getEntities: vi.fn(() => []),
    ...overrides,
  } as unknown as ConveneClient;
}

function makeServer(client: ConveneClient): Server {
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
  it("returns all six tool names", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, ListToolsRequestSchema.shape.method.value);
    expect(handler).toBeDefined();

    const result = await handler!({ method: "tools/list", params: {} }, {});
    const tools = (result as { tools: Array<{ name: string }> }).tools;
    const names = tools.map((t) => t.name);

    expect(names).toContain("reply");
    expect(names).toContain("accept_task");
    expect(names).toContain("update_status");
    expect(names).toContain("request_context");
    expect(names).toContain("get_meeting_recap");
    expect(names).toContain("get_entity_history");
    expect(names).toHaveLength(6);
  });

  it("reply tool has required text property in schema", async () => {
    const server = makeServer(makeMockClient());
    const handler = getHandler(server, ListToolsRequestSchema.shape.method.value);
    const result = await handler!({ method: "tools/list", params: {} }, {});
    const tools = (result as { tools: Array<{ name: string; inputSchema: Record<string, unknown> }> }).tools;
    const reply = tools.find((t) => t.name === "reply");
    expect(reply?.inputSchema["required"]).toContain("text");
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
// Tool handlers
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
