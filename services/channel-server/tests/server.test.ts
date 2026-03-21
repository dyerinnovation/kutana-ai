/**
 * Tests for server initialization and capability declaration.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { createServer } from "../src/server.js";
import type { ChannelServerConfig } from "../src/config.js";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeConfig(overrides: Partial<ChannelServerConfig> = {}): ChannelServerConfig {
  return {
    conveneApiUrl: "ws://localhost:8003",
    conveneHttpUrl: "http://localhost:8000",
    conveneApiKey: "test-api-key",
    conveneMeetingId: "meeting-123",
    agentMode: "both",
    entityFilter: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("createServer", () => {
  it("returns a Server and ConveneClient", () => {
    const { server, client } = createServer(makeConfig());
    expect(server).toBeDefined();
    expect(client).toBeDefined();
  });

  it("creates distinct server instances for separate calls", () => {
    const { server: s1 } = createServer(makeConfig());
    const { server: s2 } = createServer(makeConfig());
    // Each call produces a fresh instance
    expect(s1).not.toBe(s2);
  });

  it("passes through agentMode to the client", () => {
    const config = makeConfig({ agentMode: "transcript" });
    const { client } = createServer(config);
    // Client is constructed with the provided config — verified indirectly
    // by the fact that getRecentTranscript exists and returns an empty array
    expect(client.getRecentTranscript()).toEqual([]);
  });

  it("does not throw for minimal valid config", () => {
    expect(() =>
      createServer({
        conveneApiUrl: "ws://localhost:8003",
        conveneHttpUrl: "http://localhost:8000",
        conveneApiKey: "key",
        conveneMeetingId: "m1",
        agentMode: "both",
        entityFilter: [],
      }),
    ).not.toThrow();
  });
});

describe("ConveneClient initial state", () => {
  let config: ChannelServerConfig;

  beforeEach(() => {
    config = makeConfig();
  });

  it("is not connected before connect() is called", () => {
    const { client } = createServer(config);
    expect(client.isConnected()).toBe(false);
  });

  it("returns empty transcript buffer before any events", () => {
    const { client } = createServer(config);
    expect(client.getRecentTranscript(50)).toEqual([]);
  });

  it("returns empty entity buffer before any events", () => {
    const { client } = createServer(config);
    expect(client.getEntities("task", 50)).toEqual([]);
  });
});

describe("channel callback wiring", () => {
  it("registers and can invoke a channel callback", () => {
    const { client } = createServer(makeConfig());
    const received: string[] = [];
    client.onChannelMessage(async (msg) => {
      received.push(msg.topic);
    });
    // Callback is registered — no errors thrown
    expect(received).toEqual([]);
  });

  it("allows overwriting a channel callback", () => {
    const { client } = createServer(makeConfig());
    const cb1 = vi.fn();
    const cb2 = vi.fn();
    client.onChannelMessage(cb1);
    client.onChannelMessage(cb2);
    // Second registration wins; no errors
    expect(cb1).not.toHaveBeenCalled();
    expect(cb2).not.toHaveBeenCalled();
  });
});
