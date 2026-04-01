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

let lastMockWs: MockWebSocket | null = null;

class MockWebSocket extends EventEmitter {
  static OPEN = 1 as const;
  readyState: number = MockWebSocket.OPEN;
  sentMessages: string[] = [];

  constructor(_url: string, _options?: { rejectUnauthorized?: boolean }) {
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

const MEETING_ID = "meeting-abc";

function makeConfig(
  overrides: Partial<ChannelServerConfig> = {},
): ChannelServerConfig {
  return {
    conveneApiUrl: "ws://localhost:8003",
    conveneHttpUrl: "http://localhost:8000",
    conveneApiKey: "test-key",
    conveneBearerToken: "",
    conveneAgentName: "Claude Code",
    agentMode: "both",
    entityFilter: [],
    tlsRejectUnauthorized: true,
    ...overrides,
  };
}

function buildTaskEntity(id = "t1"): TaskEntity {
  return {
    id,
    entity_type: "task",
    meeting_id: MEETING_ID,
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
    meeting_id: MEETING_ID,
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
 * Create a ConveneClient backed by MockWebSocket, authenticate, and
 * join a meeting. Returns the connected client and the WS instance.
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
    MockWebSocket as unknown as ConstructorParameters<typeof ConveneClient>[1],
  );

  // joinMeeting will: (1) authenticate, (2) construct WS, (3) wait for joined
  const joinPromise = client.joinMeeting(MEETING_ID);

  // Give the event loop a tick for auth + WS construction
  await new Promise<void>((resolve) => setTimeout(resolve, 0));

  const mockWs = lastMockWs!;
  expect(mockWs, "MockWebSocket should have been constructed by now").not.toBeNull();

  // Trigger the WS "open" event → client sends join_meeting
  mockWs.emit("open");

  // Yield so the join_meeting message is sent, then reply with "joined"
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  mockWs.simulateMessage({ type: "joined", meeting_id: MEETING_ID });

  await joinPromise;
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
    expect(joinMsg?.["meeting_id"]).toBe(MEETING_ID);
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

  it("getCurrentMeetingId() returns the meeting ID after joining", async () => {
    const { client } = await setupConnectedClient(makeConfig());
    expect(client.getCurrentMeetingId()).toBe(MEETING_ID);
  });

  it("isConnected() returns false after leaveMeeting()", async () => {
    const { client } = await setupConnectedClient(makeConfig());
    await client.leaveMeeting();
    expect(client.isConnected()).toBe(false);
    expect(client.getCurrentMeetingId()).toBeNull();
  });

  it("clears buffers after leaveMeeting()", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    // Add some data to buffers
    mockWs.simulateMessage({
      type: "transcript",
      meeting_id: MEETING_ID,
      segment_id: "s1",
      speaker: "Alice",
      text: "Hello",
      start_time: 0, end_time: 1, confidence: 0.9, is_final: true,
    });
    expect(client.getRecentTranscript()).toHaveLength(1);

    await client.leaveMeeting();
    expect(client.getRecentTranscript()).toHaveLength(0);
    expect(client.getChatMessages()).toHaveLength(0);
    expect(client.getParticipants()).toHaveLength(0);
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
      meeting_id: MEETING_ID,
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
      meeting_id: MEETING_ID,
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
      meeting_id: MEETING_ID,
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
      meeting_id: MEETING_ID,
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
        meeting_id: MEETING_ID,
        active_speaker_id: "p1",
        queue: [
          { position: 1, participant_id: "p2", priority: "normal", topic: "auth fix", raised_at: "2026-03-23T10:00:00Z" },
        ],
      },
    });

    expect(received).toHaveLength(1);
    expect(received[0]?.topic).toBe("turn");
    expect(received[0]?.type).toBe("queue_updated");
  });

  it("sets isSpeaking=true on turn.your_turn", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    mockWs.simulateMessage({
      type: "event",
      event_type: "turn.your_turn",
      payload: { meeting_id: MEETING_ID },
    });

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
});

// ---------------------------------------------------------------------------
// Chat events
// ---------------------------------------------------------------------------

describe("chat events", () => {
  it("buffers inbound chat messages", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    mockWs.simulateMessage({
      type: "event",
      event_type: "data.channel.chat",
      payload: {
        sender_name: "Alice",
        sender_session_id: "s-alice",
        payload: { text: "Hello from Alice" },
      },
    });

    const messages = client.getChatMessages(10);
    expect(messages).toHaveLength(1);
    expect(messages[0]?.text).toBe("Hello from Alice");
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

  it("tracks participant join/leave events", async () => {
    const { client, mockWs } = await setupConnectedClient(makeConfig());

    mockWs.simulateMessage({
      type: "participant_update",
      action: "joined",
      participant_id: "p-new",
      name: "Dave",
      role: "human",
      connection_type: "webrtc",
    });

    expect(client.getParticipants().find((p) => p.name === "Dave")).toBeDefined();

    mockWs.simulateMessage({
      type: "participant_update",
      action: "left",
      participant_id: "p-new",
      name: "Dave",
      role: "human",
    });

    expect(client.getParticipants().find((p) => p.name === "Dave")).toBeUndefined();
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

    const joinPromise = client.joinMeeting(MEETING_ID);
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    const mockWs = lastMockWs!;
    mockWs.emit("open");
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    mockWs.simulateMessage({ type: "joined", meeting_id: MEETING_ID });
    await joinPromise;

    // fetch should NOT have been called (bearer token was used directly)
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
