/**
 * Tests for MCP resource registration and content.
 */

import { describe, it, expect, vi } from "vitest";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import {
  registerResources,
  PLATFORM_CONTEXT_DOC,
} from "../src/resources.js";
import type { KutanaClient } from "../src/kutana-client.js";
import type { ChannelServerConfig } from "../src/config.js";

// Helper to retrieve an internal request handler from the MCP Server.
function getHandler(server: Server, methodName: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access
  return (server as any)._requestHandlers.get(methodName) as
    | ((req: Record<string, unknown>, extra: unknown) => Promise<unknown>)
    | undefined;
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeMockClient(overrides: Partial<KutanaClient> = {}): KutanaClient {
  return {
    isConnected: vi.fn(() => true),
    getCurrentMeetingId: vi.fn(() => "meeting-123"),
    getRecentTranscript: vi.fn(() => []),
    getEntities: vi.fn(() => []),
    getParticipants: vi.fn(() => []),
    onChannelMessage: vi.fn(),
    authenticate: vi.fn(),
    joinMeeting: vi.fn(),
    leaveMeeting: vi.fn(),
    listMeetings: vi.fn(),
    createMeeting: vi.fn(),
    sendChatMessage: vi.fn(),
    acceptTask: vi.fn(),
    updateTaskStatus: vi.fn(),
    ...overrides,
  } as unknown as KutanaClient;
}

function makeConfig(overrides: Partial<ChannelServerConfig> = {}): ChannelServerConfig {
  return {
    kutanaApiUrl: "ws://localhost:8003",
    kutanaHttpUrl: "http://localhost:8000",
    kutanaApiKey: "key",
    kutanaBearerToken: "",
    kutanaAgentName: "Claude Code",
    agentMode: "both",
    entityFilter: [],
    tlsRejectUnauthorized: true,
    ...overrides,
  };
}

function makeServer(
  client: KutanaClient,
  config: ChannelServerConfig,
): Server {
  const server = new Server(
    { name: "test", version: "0.0.0" },
    { capabilities: { resources: { listChanged: true } } },
  );
  registerResources(server, client, config);
  return server;
}

// ---------------------------------------------------------------------------
// List resources
// ---------------------------------------------------------------------------

describe("list resources", () => {
  it("includes kutana://platform/context", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ListResourcesRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/list", params: {} },
      {},
    );
    const res = result as { resources: Array<{ uri: string }> };
    const uris = res.resources.map((r) => r.uri);
    expect(uris).toContain("kutana://platform/context");
  });
});

describe("list resource templates", () => {
  it("includes meeting resource templates", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ListResourceTemplatesRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/templates/list", params: {} },
      {},
    );
    const res = result as { resourceTemplates: Array<{ uriTemplate: string }> };
    const templates = res.resourceTemplates.map((t) => t.uriTemplate);
    expect(templates).toContain("kutana://meeting/{meeting_id}");
    expect(templates).toContain("kutana://meeting/{meeting_id}/context");
    expect(templates).toContain("kutana://meeting/{meeting_id}/transcript");
  });
});

// ---------------------------------------------------------------------------
// Read platform context
// ---------------------------------------------------------------------------

describe("read kutana://platform/context", () => {
  it("returns the platform context document", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "kutana://platform/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string; mimeType?: string }> };
    expect(res.contents[0]?.text).toBe(PLATFORM_CONTEXT_DOC);
    expect(res.contents[0]?.mimeType).toBe("text/markdown");
  });

  it("platform context mentions key tools", () => {
    const tools = [
      "list_meetings",
      "join_meeting",
      "reply",
      "accept_task",
      "raise_hand",
      "request_context",
      "get_meeting_recap",
    ];
    for (const tool of tools) {
      expect(PLATFORM_CONTEXT_DOC).toContain(tool);
    }
  });

  it("platform context explains all 7 insight types", () => {
    const types = [
      "task",
      "decision",
      "question",
      "entity_mention",
      "key_point",
      "blocker",
      "follow_up",
    ];
    for (const t of types) {
      expect(PLATFORM_CONTEXT_DOC).toContain(t);
    }
  });
});

// ---------------------------------------------------------------------------
// Read meeting context resource template
// ---------------------------------------------------------------------------

describe("read kutana://meeting/{id}/context", () => {
  it("returns markdown for the given meeting ID", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "kutana://meeting/meeting-123/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("meeting-123");
  });

  it("shows connected status when connected to the meeting", async () => {
    const client = makeMockClient({ getCurrentMeetingId: vi.fn(() => "m1") });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "kutana://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Connected");
  });

  it("shows disconnected status when not connected to the meeting", async () => {
    const client = makeMockClient({ getCurrentMeetingId: vi.fn(() => null) });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "kutana://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Not connected");
  });
});

describe("read kutana://meeting/{id}/transcript", () => {
  it("returns transcript when connected", async () => {
    const segments = [
      {
        type: "transcript" as const,
        meeting_id: "m1",
        segment_id: "s1",
        speaker: "Alice",
        text: "Hello",
        start_time: 1.0,
        end_time: 2.0,
        confidence: 0.9,
        is_final: true,
      },
    ];
    const client = makeMockClient({
      getCurrentMeetingId: vi.fn(() => "m1"),
      getRecentTranscript: vi.fn(() => segments),
    });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "kutana://meeting/m1/transcript" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Alice");
  });

  it("returns error when not connected to the meeting", async () => {
    const client = makeMockClient({ getCurrentMeetingId: vi.fn(() => null) });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "kutana://meeting/m1/transcript" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Not connected");
  });
});

describe("unknown resource URI", () => {
  it("throws for an unrecognised URI", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    await expect(
      handler!(
        { method: "resources/read", params: { uri: "kutana://unknown/resource" } },
        {},
      ),
    ).rejects.toThrow(/Unknown resource URI/);
  });
});
