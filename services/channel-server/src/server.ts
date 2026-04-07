/**
 * Kutana AI Claude Code Channel Server
 *
 * MCP server that bridges Kutana AI meetings to Claude Code. Provides
 * tools for meeting discovery, joining, chat, turn management, and
 * real-time event forwarding via channel notifications.
 *
 * Run with:
 *
 *   bun src/server.ts
 *
 * Required environment variables:
 *   KUTANA_API_KEY      — agent API key (from Kutana dashboard)
 *
 * Optional:
 *   KUTANA_URL          — single base URL (e.g. https://kutana.spark-b0f2.local);
 *                         derives both WebSocket and HTTP URLs automatically
 *   KUTANA_API_URL      — WebSocket URL of the agent gateway (overrides KUTANA_URL)
 *   KUTANA_HTTP_URL     — HTTP URL of the API server (overrides KUTANA_URL)
 *   KUTANA_AGENT_MODE   — transcript | insights | both | selective
 *   KUTANA_ENTITY_FILTER — comma-separated entity types for selective mode
 *   KUTANA_TLS_REJECT_UNAUTHORIZED — set "0" to allow self-signed certs (default)
 */

import { fileURLToPath } from "url";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { ServerCapabilities } from "@modelcontextprotocol/sdk/types.js";
import { KutanaClient } from "./kutana-client.js";
import { loadConfig, resolveEndpoints } from "./config.js";
import { registerTools } from "./tools.js";
import {
  registerResources,
  notifyResourcesChanged,
} from "./resources.js";
import type { ChannelMessage } from "./types.js";

// ---------------------------------------------------------------------------
// Platform instructions (Layer 1 context — sent during MCP initialize)
// ---------------------------------------------------------------------------

const CHANNEL_INSTRUCTIONS = `Events from the kutana-ai channel arrive as <channel source="kutana-ai" topic="..." type="...">.
They contain real-time meeting data: transcript segments, chat messages, speaker queue changes,
and extracted insights (tasks, decisions, questions, blockers).
Use the kutana tools (list_meetings, join_meeting, reply, raise_hand, etc.) to interact.
Reply with the reply tool when you want to send a message to the meeting chat.

Start by listing available meetings with list_meetings, or join one with join_meeting.`;

// ---------------------------------------------------------------------------
// Server capabilities
// ---------------------------------------------------------------------------

type ExtendedCapabilities = ServerCapabilities & {
  experimental: { "claude/channel": Record<string, never> };
};

// ---------------------------------------------------------------------------
// Main server factory — exported for testability
// ---------------------------------------------------------------------------

/** Create and return a configured MCP Server instance with a KutanaClient. */
export function createServer(config: ReturnType<typeof loadConfig>): {
  server: Server;
  client: KutanaClient;
} {
  const capabilities: ExtendedCapabilities = {
    tools: {},
    resources: { subscribe: true, listChanged: true },
    experimental: { "claude/channel": {} },
  };

  const server = new Server(
    { name: "kutana-ai", version: "0.2.0" },
    {
      capabilities,
      ...({ instructions: CHANNEL_INSTRUCTIONS } as object),
    },
  );

  const client = new KutanaClient(config);

  // Callback for tools to notify resource changes on join/leave
  const onMeetingStateChange = async () => {
    await notifyResourcesChanged(server);
  };

  registerTools(server, client, onMeetingStateChange);
  registerResources(server, client, config);

  // Forward Kutana events → Claude Code channel notifications
  client.onChannelMessage(async (msg: ChannelMessage) => {
    try {
      await server.notification({
        method: "notifications/claude/channel",
        params: {
          content: msg.content,
          meta: {
            topic: msg.topic,
            type: msg.type,
            ...(msg.metadata ?? {}),
          },
        },
      });
    } catch (err) {
      // Notification errors (e.g. client disconnected) should not crash the server
      process.stderr.write(
        `[channel-server] Notification error: ${String(err)}\n`,
      );
    }
  });

  return { server, client };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const config = loadConfig();

  if (!config.kutanaApiKey) {
    process.stderr.write(
      "[channel-server] Error: KUTANA_API_KEY environment variable is required\n",
    );
    process.exit(1);
  }

  // Apply TLS setting for self-signed certs
  if (!config.tlsRejectUnauthorized) {
    process.env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0";
  }

  // Resolve endpoints via discovery before creating the client
  await resolveEndpoints(config);

  const { server, client } = createServer(config);

  // Connect the MCP transport (STDIO)
  const transport = new StdioServerTransport();
  await server.connect(transport);

  process.stderr.write(
    `[channel-server] MCP server started (mode: ${config.agentMode})\n`,
  );

  // Authenticate so list_meetings and other API calls work immediately
  try {
    await client.authenticate();
    process.stderr.write("[channel-server] Authenticated with Kutana API\n");
  } catch (err) {
    // Auth failure is logged but doesn't kill the server — tools will
    // attempt re-auth on first use.
    process.stderr.write(
      `[channel-server] Warning: authentication failed — ${String(err)}\n`,
    );
  }

  // Graceful shutdown
  process.on("SIGINT", async () => {
    process.stderr.write("[channel-server] Shutting down...\n");
    if (client.getCurrentMeetingId()) {
      await client.leaveMeeting();
    }
    process.exit(0);
  });

  process.on("SIGTERM", async () => {
    if (client.getCurrentMeetingId()) {
      await client.leaveMeeting();
    }
    process.exit(0);
  });
}

// Only run main() when this file is the entry point (not when imported by tests).
// Uses process.argv[1] check instead of Bun-specific import.meta.main so it
// works under both Bun and Node.js/tsx.
const isEntryPoint = process.argv[1] === fileURLToPath(import.meta.url);
if (isEntryPoint) {
  main().catch((err: unknown) => {
    process.stderr.write(`[channel-server] Fatal: ${String(err)}\n`);
    process.exit(1);
  });
}
