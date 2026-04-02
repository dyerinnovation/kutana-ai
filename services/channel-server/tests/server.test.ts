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
    kutanaApiUrl: "ws://localhost:8003",
    kutanaHttpUrl: "http://localhost:8000",
    kutanaApiKey: "test-api-key",
    kutanaBearerToken: "",
    kutanaAgentName: "Claude Code",
    agentMode: "both",
    entityFilter: [],
    tlsRejectUnauthorized: true,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("createServer", () => {
  it("returns a Server and KutanaClient", () => {
    const { server, client } = createServer(makeConfig());
    expect(server).toBeDefined();
    expect(client).toBeDefined();
  });

  it("creates distinct server instances for separate calls", () => {
    const { server: s1 } = createServer(makeConfig());
    const { server: s2 } = createServer(makeConfig());
    expect(s1).not.toBe(s2);
  });

  it("passes through agentMode to the client", () => {
    const config = makeConfig({ agentMode: "transcript" });
    const { client } = createServer(config);
    expect(client.getRecentTranscript()).toEqual([]);
  });

  it("does not throw for minimal valid config", () => {
    expect(() =>
      createServer({
        kutanaApiUrl: "ws://localhost:8003",
        kutanaHttpUrl: "http://localhost:8000",
        kutanaApiKey: "key",
        kutanaBearerToken: "",
        kutanaAgentName: "Claude Code",
        agentMode: "both",
        entityFilter: [],
        tlsRejectUnauthorized: true,
      }),
    ).not.toThrow();
  });
});

describe("KutanaClient initial state", () => {
  let config: ChannelServerConfig;

  beforeEach(() => {
    config = makeConfig();
  });

  it("is not connected before joining a meeting", () => {
    const { client } = createServer(config);
    expect(client.isConnected()).toBe(false);
  });

  it("has no current meeting before joining", () => {
    const { client } = createServer(config);
    expect(client.getCurrentMeetingId()).toBeNull();
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
    expect(received).toEqual([]);
  });

  it("allows overwriting a channel callback", () => {
    const { client } = createServer(makeConfig());
    const cb1 = vi.fn();
    const cb2 = vi.fn();
    client.onChannelMessage(cb1);
    client.onChannelMessage(cb2);
    expect(cb1).not.toHaveBeenCalled();
    expect(cb2).not.toHaveBeenCalled();
  });
});
