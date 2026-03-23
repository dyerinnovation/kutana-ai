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
    conveneBearerToken: "",
    conveneMeetingId: "meeting-abc",
    conveneAgentName: "Claude Code",
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

// ---------------------------------------------------------------------------
// Turn management events
// ---------------------------------------------------------------------------

describe("turn management events", () => {
  it("forwards turn.queue.updated as a turn channel message", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "turn.queue.updated",
      payload: {
        meeting_id: "meeting-abc",
        active_speaker_id: "p1",
        queue: [
          { position: 1, participant_id: "p2", priority: "normal", topic: "auth fix", raised_at: "2026-03-23T10:00:00Z" },
        ],
      },
    });

    expect(received).toHaveLength(1);
    expect(received[0]?.topic).toBe("turn");
    expect(received[0]?.type).toBe("queue_updated");
    expect(received[0]?.content).toContain("p1");
  });

  it("buffers the last queue status from turn.queue.updated", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    mockWs.simulateMessage({
      type: "event",
      event_type: "turn.queue.updated",
      payload: {
        meeting_id: "meeting-abc",
        active_speaker_id: "p-speaker",
        queue: [],
      },
    });

    const status = client.getLastQueueStatus();
    expect(status).not.toBeNull();
    expect(status?.active_speaker_id).toBe("p-speaker");
  });

  it("forwards turn.speaker.changed as a turn channel message", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "turn.speaker.changed",
      payload: {
        meeting_id: "meeting-abc",
        previous_speaker_id: "p1",
        new_speaker_id: "p2",
      },
    });

    expect(received).toHaveLength(1);
    expect(received[0]?.topic).toBe("turn");
    expect(received[0]?.type).toBe("speaker_changed");
    expect(received[0]?.content).toContain("p1");
    expect(received[0]?.content).toContain("p2");
  });

  it("sets isSpeaking=true and isInQueue=false on turn.your_turn", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "turn.your_turn",
      payload: { meeting_id: "meeting-abc" },
    });

    expect(received).toHaveLength(1);
    expect(received[0]?.type).toBe("your_turn");

    const { isSpeaking, isInQueue } = client.getSpeakingStatus();
    expect(isSpeaking).toBe(true);
    expect(isInQueue).toBe(false);
  });

  it("raiseHand sends raise_hand WebSocket message", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    await client.raiseHand("urgent", "blocking issue");

    const raiseMsg = mockWs.sentMessages
      .map((m) => JSON.parse(m) as Record<string, unknown>)
      .find((m) => m["type"] === "raise_hand");

    expect(raiseMsg).toBeDefined();
    expect(raiseMsg?.["priority"]).toBe("urgent");
    expect(raiseMsg?.["topic"]).toBe("blocking issue");
  });

  it("finishedSpeaking sends finished_speaking WebSocket message", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    await client.finishedSpeaking();

    const msg = mockWs.sentMessages
      .map((m) => JSON.parse(m) as Record<string, unknown>)
      .find((m) => m["type"] === "finished_speaking");

    expect(msg).toBeDefined();
  });

  it("lowerHand sends lower_hand WebSocket message", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());
    // Must be in queue first
    client["isInQueue"] = true;

    await client.lowerHand("hr-uuid");

    const msg = mockWs.sentMessages
      .map((m) => JSON.parse(m) as Record<string, unknown>)
      .find((m) => m["type"] === "lower_hand");

    expect(msg).toBeDefined();
    expect(msg?.["hand_raise_id"]).toBe("hr-uuid");
  });
});

// ---------------------------------------------------------------------------
// Chat events
// ---------------------------------------------------------------------------

describe("chat events", () => {
  it("buffers inbound chat messages from data.channel.chat events", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.chat",
      payload: {
        meeting_id: "meeting-abc",
        sender_name: "Alice",
        sender_session_id: "s-alice",
        payload: { text: "Hello from Alice" },
      },
    });

    const messages = client.getChatMessages(10);
    expect(messages).toHaveLength(1);
    expect(messages[0]?.text).toBe("Hello from Alice");
    expect(messages[0]?.sender_name).toBe("Alice");
  });

  it("forwards inbound chat as a 'chat' topic channel message", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.chat",
      payload: {
        meeting_id: "meeting-abc",
        sender_name: "Bob",
        sender_session_id: "s-bob",
        payload: { text: "Good morning" },
      },
    });

    expect(received).toHaveLength(1);
    expect(received[0]?.topic).toBe("chat");
    expect(received[0]?.type).toBe("chat_message");
    expect(received[0]?.content).toContain("Bob");
    expect(received[0]?.content).toContain("Good morning");
  });

  it("assigns monotonically increasing indexes to chat messages", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    for (const text of ["First", "Second", "Third"]) {
      mockWs.simulateMessage({
        type: "event",
        event_type: "data.channel.chat",
        payload: { sender_name: "Alice", sender_session_id: "s1", payload: { text } },
      });
    }

    const messages = client.getChatMessages(10);
    expect(messages).toHaveLength(3);
    expect(messages[0]?.index).toBe(0);
    expect(messages[1]?.index).toBe(1);
    expect(messages[2]?.index).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Participant tracking
// ---------------------------------------------------------------------------

describe("participant tracking", () => {
  it("adds self as claude-code participant on join", async () => {
    const { client } = await setupConnectedClient(makeConfig());

    const participants = client.getParticipants();
    const self = participants.find((p) => p.name === "Claude Code");
    expect(self).toBeDefined();
    expect(self?.source).toBe("claude-code");
  });

  it("forwards participant_update joined events", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    const received: ChannelMessage[] = [];
    client.onChannelMessage((msg) => { received.push(msg); });

    mockWs.simulateMessage({
      type: "participant_update",
      action: "joined",
      participant_id: "p-new",
      name: "Dave",
      role: "human",
      connection_type: "webrtc",
    });

    const turnAndParticipantMsgs = received.filter((m) => m.topic === "participant");
    expect(turnAndParticipantMsgs).toHaveLength(1);
    expect(turnAndParticipantMsgs[0]?.type).toBe("joined");
    expect(turnAndParticipantMsgs[0]?.content).toContain("Dave");

    // Also added to buffer
    const participants = client.getParticipants();
    expect(participants.find((p) => p.name === "Dave")).toBeDefined();
  });

  it("removes participant from buffer on participant_update left", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    // Add a participant first
    mockWs.simulateMessage({
      type: "participant_update",
      action: "joined",
      participant_id: "p-eve",
      name: "Eve",
      role: "human",
      connection_type: "webrtc",
    });

    expect(client.getParticipants().find((p) => p.name === "Eve")).toBeDefined();

    mockWs.simulateMessage({
      type: "participant_update",
      action: "left",
      participant_id: "p-eve",
      name: "Eve",
      role: "human",
    });

    expect(client.getParticipants().find((p) => p.name === "Eve")).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Bearer token auth
// ---------------------------------------------------------------------------

describe("bearer token auth", () => {
  it("skips API key exchange when CONVENE_BEARER_TOKEN is set", async () => {
    const config = makeConfig({ conveneBearerToken: "pre-issued-jwt" });

    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const client = new ConveneClient(
      config,
      MockWebSocket as unknown as ConstructorParameters<typeof ConveneClient>[1],
    );

    const connectPromise = client.connect();
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    const mockWs = lastMockWs!;
    mockWs.emit("open");
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    mockWs.simulateMessage({ type: "joined", meeting_id: config.conveneMeetingId });
    await connectPromise;

    // fetch should NOT have been called (bearer token was used directly)
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
