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
import type { ConveneClient } from "../src/convene-client.js";
import type { ChannelServerConfig } from "../src/config.js";

// Helper to retrieve an internal request handler from the MCP Server.
// The SDK stores handlers in the private `_requestHandlers` Map.
function getHandler(server: Server, methodName: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unsafe-member-access
  return (server as any)._requestHandlers.get(methodName) as
    | ((req: Record<string, unknown>, extra: unknown) => Promise<unknown>)
    | undefined;
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeMockClient(overrides: Partial<ConveneClient> = {}): ConveneClient {
  return {
    isConnected: vi.fn(() => true),
    getRecentTranscript: vi.fn(() => []),
    getEntities: vi.fn(() => []),
    onChannelMessage: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendChatMessage: vi.fn(),
    acceptTask: vi.fn(),
    updateTaskStatus: vi.fn(),
    ...overrides,
  } as unknown as ConveneClient;
}

function makeConfig(overrides: Partial<ChannelServerConfig> = {}): ChannelServerConfig {
  return {
    conveneApiUrl: "ws://localhost:8003",
    conveneHttpUrl: "http://localhost:8000",
    conveneApiKey: "key",
    conveneMeetingId: "meeting-123",
    agentMode: "both",
    entityFilter: [],
    ...overrides,
  };
}

function makeServer(
  client: ConveneClient,
  config: ChannelServerConfig,
): Server {
  const server = new Server(
    { name: "test", version: "0.0.0" },
    { capabilities: { resources: {} } },
  );
  registerResources(server, client, config);
  return server;
}

// ---------------------------------------------------------------------------
// List resources
// ---------------------------------------------------------------------------

describe("list resources", () => {
  it("includes convene://platform/context", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ListResourcesRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/list", params: {} },
      {},
    );
    const res = result as { resources: Array<{ uri: string }> };
    const uris = res.resources.map((r) => r.uri);
    expect(uris).toContain("convene://platform/context");
  });
});

describe("list resource templates", () => {
  it("includes convene://meeting/{meeting_id}/context template", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ListResourceTemplatesRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/templates/list", params: {} },
      {},
    );
    const res = result as { resourceTemplates: Array<{ uriTemplate: string }> };
    const templates = res.resourceTemplates.map((t) => t.uriTemplate);
    expect(templates).toContain("convene://meeting/{meeting_id}/context");
  });
});

// ---------------------------------------------------------------------------
// Read platform context
// ---------------------------------------------------------------------------

describe("read convene://platform/context", () => {
  it("returns the platform context document", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://platform/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string; mimeType?: string }> };
    expect(res.contents[0]?.text).toBe(PLATFORM_CONTEXT_DOC);
    expect(res.contents[0]?.mimeType).toBe("text/markdown");
  });

  it("platform context mentions all six tools", () => {
    const tools = [
      "reply",
      "accept_task",
      "update_status",
      "request_context",
      "get_meeting_recap",
      "get_entity_history",
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

describe("read convene://meeting/{id}/context", () => {
  it("returns markdown for the given meeting ID", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://meeting/abc-123/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("abc-123");
  });

  it("shows connected status when client is connected", async () => {
    const client = makeMockClient({ isConnected: vi.fn(() => true) });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Connected");
  });

  it("shows disconnected status when client is not connected", async () => {
    const client = makeMockClient({ isConnected: vi.fn(() => false) });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Not connected");
  });

  it("includes agent mode in context", async () => {
    const config = makeConfig({ agentMode: "transcript" });
    const server = makeServer(makeMockClient(), config);
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("transcript");
  });

  it("includes selective filter list when agentMode is selective", async () => {
    const config = makeConfig({
      agentMode: "selective",
      entityFilter: ["task", "blocker"],
    });
    const server = makeServer(makeMockClient(), config);
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("task");
    expect(res.contents[0]?.text).toContain("blocker");
  });

  it("includes transcript preview when segments are available", async () => {
    const segments = [
      {
        type: "transcript" as const,
        meeting_id: "m1",
        segment_id: "s1",
        speaker: "Alice",
        text: "Let's discuss the roadmap",
        start_time: 10.5,
        end_time: 13.0,
        confidence: 0.95,
        is_final: true,
      },
    ];
    const client = makeMockClient({ getRecentTranscript: vi.fn(() => segments) });
    const server = makeServer(client, makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    const result = await handler!(
      { method: "resources/read", params: { uri: "convene://meeting/m1/context" } },
      {},
    );
    const res = result as { contents: Array<{ text: string }> };
    expect(res.contents[0]?.text).toContain("Alice");
    expect(res.contents[0]?.text).toContain("roadmap");
  });
});

describe("unknown resource URI", () => {
  it("throws for an unrecognised URI", async () => {
    const server = makeServer(makeMockClient(), makeConfig());
    const handler = getHandler(server, ReadResourceRequestSchema.shape.method.value);

    await expect(
      handler!(
        { method: "resources/read", params: { uri: "convene://unknown/resource" } },
        {},
      ),
    ).rejects.toThrow(/Unknown resource URI/);
  });
});
