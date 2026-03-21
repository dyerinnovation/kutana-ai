/**
 * Tests for ConveneClient event forwarding and agent mode filtering.
 *
 * A capturing MockWebSocket class is used so that the ConveneClient's
 * internal WebSocket instance (created via `new this.WS(url)`) is the same
 * object that the test drives with `simulateMessage()`.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { EventEmitter } from "node:events";
import { ConveneClient } from "../src/convene-client.js";
import type { ChannelServerConfig } from "../src/config.js";
import type { ChannelMessage, TaskEntity, DecisionEntity } from "../src/types.js";

// ---------------------------------------------------------------------------
// MockWebSocket — captures the instance created by ConveneClient
// ---------------------------------------------------------------------------

/** Last MockWebSocket instance constructed — set by the MockWS constructor. */
let lastMockWs: MockWebSocket | null = null;

class MockWebSocket extends EventEmitter {
  static OPEN = 1 as const;
  readyState: number = MockWebSocket.OPEN;
  sentMessages: string[] = [];

  constructor(_url: string) {
    super();
    lastMockWs = this;
  }

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.emit("close");
  }

  simulateMessage(payload: Record<string, unknown>): void {
    this.emit("message", Buffer.from(JSON.stringify(payload)));
  }

  simulateError(message: string): void {
    this.emit("error", new Error(message));
  }
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

beforeEach(() => {
  lastMockWs = null;
});

function makeConfig(
  overrides: Partial<ChannelServerConfig> = {},
): ChannelServerConfig {
  return {
    conveneApiUrl: "ws://localhost:8003",
    conveneHttpUrl: "http://localhost:8000",
    conveneApiKey: "test-key",
    conveneMeetingId: "meeting-abc",
    agentMode: "both",
    entityFilter: [],
    ...overrides,
  };
}

function buildTaskEntity(id = "t1"): TaskEntity {
  return {
    id,
    entity_type: "task",
    meeting_id: "meeting-abc",
    confidence: 0.9,
    extracted_at: new Date().toISOString(),
    batch_id: "b1",
    title: "Write tests",
    assignee: null,
    deadline: null,
    priority: "medium",
    status: "identified",
    source_speaker: null,
    source_segment_id: null,
  };
}

function buildDecisionEntity(id = "d1"): DecisionEntity {
  return {
    id,
    entity_type: "decision",
    meeting_id: "meeting-abc",
    confidence: 0.85,
    extracted_at: new Date().toISOString(),
    batch_id: "b1",
    summary: "Use TypeScript for all new services",
    participants: ["Alice", "Bob"],
    rationale: "Better type safety",
    source_segment_ids: [],
  };
}

/**
 * Create a ConveneClient backed by MockWebSocket and simulate the gateway
 * join handshake.  Returns the connected client and the WS instance.
 */
async function setupConnectedClient(
  config: ChannelServerConfig,
): Promise<{ client: ConveneClient; mockWs: MockWebSocket }> {
  // Stub fetch for the auth token exchange
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
    ok: true,
    json: async () => ({ token: "test-jwt-token" }),
  } as Response);

  const client = new ConveneClient(
    config,
    // MockWebSocket sets `lastMockWs = this` in its constructor, so after
    // `new this.WS(url)` runs we can reference the exact instance the client
    // is using.
    MockWebSocket as unknown as ConstructorParameters<typeof ConveneClient>[1],
  );

  // Start connect() — it will: (1) authenticate, (2) construct WS, (3) wait for joined
  const connectPromise = client.connect();

  // authenticate() is a microtask (mocked fetch resolves immediately).
  // After that microtask resolves, connectWebSocket() synchronously calls
  // new this.WS(url) which sets lastMockWs.  Give the event loop one tick
  // to complete that, then drive the WS lifecycle.
  await new Promise<void>((resolve) => setTimeout(resolve, 0));

  const mockWs = lastMockWs!;
  expect(mockWs, "MockWebSocket should have been constructed by now").not.toBeNull();

  // Trigger the WS "open" event → client sends join_meeting
  mockWs.emit("open");

  // Yield so the join_meeting message is sent, then reply with "joined"
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  mockWs.simulateMessage({ type: "joined", meeting_id: config.conveneMeetingId });

  // Wait for connectPromise to resolve
  await connectPromise;
  fetchSpy.mockRestore();

  return { client, mockWs };
}

// ---------------------------------------------------------------------------
// Connection behaviour
// ---------------------------------------------------------------------------

describe("ConveneClient connection", () => {
  it("sends join_meeting after WebSocket open", async () => {
    const { mockWs } = await setupConnectedClient(makeConfig());
    const joinMsg = mockWs.sentMessages
      .map((m) => JSON.parse(m) as Record<string, unknown>)
      .find((m) => m["type"] === "join_meeting");

    expect(joinMsg).toBeDefined();
    expect(joinMsg?.["meeting_id"]).toBe("meeting-abc");
  });

  it("subscribes to insight channels after joining", async () => {
    const { mockWs } = await setupConnectedClient(makeConfig());
    const subMsg = mockWs.sentMessages
      .map((m) => JSON.parse(m) as Record<string, unknown>)
      .find((m) => m["type"] === "subscribe_channel");

    expect(subMsg).toBeDefined();
    const channels = subMsg?.["channels"] as string[] | undefined;
    expect(channels).toContain("insights");
  });

  it("isConnected() returns true after joining", async () => {
    const { client } = await setupConnectedClient(makeConfig());
    expect(client.isConnected()).toBe(true);
  });

  it("isConnected() returns false after disconnect()", async () => {
    const { client } = await setupConnectedClient(makeConfig());
    await client.disconnect();
    expect(client.isConnected()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// transcript mode
// ---------------------------------------------------------------------------

describe("agentMode: transcript", () => {
  it("forwards transcript segments to channel callback", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "transcript" }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: "meeting-abc",
      segment_id: "s1",
      speaker: "Alice",
      text: "Hello everyone",
      start_time: 0, end_time: 2, confidence: 0.95, is_final: true,
    });

    expect(received).toHaveLength(1);
    expect(received[0]?.topic).toBe("transcript");
    expect(received[0]?.content).toContain("Alice");
    expect(received[0]?.content).toContain("Hello everyone");
  });

  it("does NOT forward insight events", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "transcript" }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: { batch_id: "b1", entities: [buildTaskEntity()], processing_time_ms: 50 },
    });

    expect(received).toHaveLength(0);
  });

  it("buffers transcript segments for request_context", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "transcript" }),
    );

    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: "meeting-abc",
      segment_id: "s1",
      speaker: "Bob",
      text: "We need to deploy by Friday",
      start_time: 5, end_time: 7, confidence: 0.9, is_final: true,
    });

    const buffer = client.getRecentTranscript(10);
    expect(buffer).toHaveLength(1);
    expect(buffer[0]?.text).toContain("Friday");
  });
});

// ---------------------------------------------------------------------------
// insights mode
// ---------------------------------------------------------------------------

describe("agentMode: insights", () => {
  it("forwards insight entities to channel callback", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "insights" }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: {
        batch_id: "b1",
        entities: [buildTaskEntity(), buildDecisionEntity()],
        processing_time_ms: 80,
      },
    });

    expect(received).toHaveLength(2);
    expect(received[0]?.topic).toBe("insight");
    expect(received[0]?.type).toBe("task");
    expect(received[1]?.type).toBe("decision");
  });

  it("does NOT forward transcript segments", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "insights" }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: "meeting-abc",
      segment_id: "s1",
      speaker: "Alice",
      text: "Hello",
      start_time: 0, end_time: 1, confidence: 0.9, is_final: true,
    });

    expect(received).toHaveLength(0);
  });

  it("buffers entities for get_entity_history", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "insights" }),
    );

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: {
        batch_id: "b1",
        entities: [buildTaskEntity("t1"), buildTaskEntity("t2")],
        processing_time_ms: 60,
      },
    });

    const entities = client.getEntities("task", 50);
    expect(entities).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// both mode
// ---------------------------------------------------------------------------

describe("agentMode: both", () => {
  it("forwards both transcript and insights", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "both" }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: "meeting-abc",
      segment_id: "s1",
      speaker: "Alice",
      text: "Let's talk about tasks",
      start_time: 0, end_time: 2, confidence: 0.9, is_final: true,
    });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: {
        batch_id: "b1",
        entities: [buildTaskEntity()],
        processing_time_ms: 40,
      },
    });

    expect(received).toHaveLength(2);
    const topics = received.map((m) => m.topic);
    expect(topics).toContain("transcript");
    expect(topics).toContain("insight");
  });
});

// ---------------------------------------------------------------------------
// selective mode
// ---------------------------------------------------------------------------

describe("agentMode: selective", () => {
  it("forwards only entity types in the filter", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "selective", entityFilter: ["task"] }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: {
        batch_id: "b1",
        entities: [buildTaskEntity(), buildDecisionEntity()],
        processing_time_ms: 50,
      },
    });

    // Only task should pass; decision is filtered out
    expect(received).toHaveLength(1);
    expect(received[0]?.type).toBe("task");
  });

  it("passes all entities when entityFilter is empty", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "selective", entityFilter: [] }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: {
        batch_id: "b1",
        entities: [buildTaskEntity(), buildDecisionEntity()],
        processing_time_ms: 50,
      },
    });

    expect(received).toHaveLength(2);
  });

  it("does NOT forward transcript in selective mode", async () => {
    const { client, mockWs } = await setupConnectedClient(
      makeConfig({ agentMode: "selective", entityFilter: ["task"] }),
    );

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: "meeting-abc",
      segment_id: "s1",
      speaker: "Alice",
      text: "Hello",
      start_time: 0, end_time: 1, confidence: 0.9, is_final: true,
    });

    expect(received).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Message formatting
// ---------------------------------------------------------------------------

describe("channel message formatting", () => {
  it("formats transcript content with speaker and timestamps", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: "meeting-abc",
      segment_id: "s1",
      speaker: "Charlie",
      text: "The deadline is next week",
      start_time: 12.5, end_time: 15.0, confidence: 0.9, is_final: true,
    });

    const content = received[0]?.content ?? "";
    expect(content).toMatch(/<transcript>/);
    expect(content).toContain("Charlie");
    expect(content).toContain("12.5s");
    expect(content).toContain("The deadline is next week");
  });

  it("formats insight content as XML with entity_type attribute", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.insights",
      payload: {
        batch_id: "b1",
        entities: [buildDecisionEntity()],
        processing_time_ms: 30,
      },
    });

    const content = received[0]?.content ?? "";
    expect(content).toMatch(/<insight type="decision">/);
    expect(content).toContain("TypeScript");
  });
});
