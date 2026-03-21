/**
 * Convene AI Claude Code Channel Server
 *
 * MCP server that bridges Convene AI meeting events to Claude Code via the
 * claude/channel protocol.  Run with:
 *
 *   bun src/server.ts
 *
 * Required environment variables:
 *   CONVENE_API_KEY      — agent API key (from Convene dashboard)
 *   CONVENE_MEETING_ID   — UUID of the meeting to join
 *
 * Optional:
 *   CONVENE_API_URL      — WebSocket URL of the agent gateway (default: ws://localhost:8003)
 *   CONVENE_HTTP_URL     — HTTP URL of the API server (default: derived from API URL)
 *   CONVENE_AGENT_MODE   — transcript | insights | both | selective (default: both)
 *   CONVENE_ENTITY_FILTER — comma-separated entity types for selective mode
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import type { ServerCapabilities } from "@modelcontextprotocol/sdk/types.js";
import { ConveneClient } from "./convene-client.js";
import { loadConfig } from "./config.js";
import { registerTools } from "./tools.js";
import { registerResources, PLATFORM_CONTEXT_DOC } from "./resources.js";
import type { ChannelMessage } from "./types.js";

// ---------------------------------------------------------------------------
// Platform instructions (Layer 1 context — sent during MCP initialize)
// ---------------------------------------------------------------------------

const PLATFORM_INSTRUCTIONS = `You are an AI agent participating in a Convene AI meeting.

${PLATFORM_CONTEXT_DOC}

You will receive real-time transcript segments and extracted meeting insights as channel
notifications. Listen actively, claim relevant tasks with accept_task, and communicate
via the reply tool.`;

// ---------------------------------------------------------------------------
// Server capabilities including the claude/channel extension
// ---------------------------------------------------------------------------

// The claude/channel capability tells Claude Code this server pushes channel
// notifications and that the model should receive them as ambient context.
type ExtendedCapabilities = ServerCapabilities & {
  "claude/channel": Record<string, never>;
};

// ---------------------------------------------------------------------------
// Main server factory — exported for testability
// ---------------------------------------------------------------------------

/** Create and return a configured MCP Server instance with a ConveneClient. */
export function createServer(config: ReturnType<typeof loadConfig>): {
  server: Server;
  client: ConveneClient;
} {
  const capabilities: ExtendedCapabilities = {
    tools: {},
    resources: { subscribe: true },
    "claude/channel": {},
  };

  const server = new Server(
    { name: "convene-ai", version: "0.1.0" },
    {
      capabilities,
      // The MCP SDK passes any extra ServerOptions fields through to the
      // InitializeResult, including `instructions` (supported since MCP 2024-11-05).
      ...({ instructions: PLATFORM_INSTRUCTIONS } as object),
    },
  );

  const client = new ConveneClient(config);

  registerTools(server, client);
  registerResources(server, client, config);

  // Forward Convene events → MCP channel notifications
  client.onChannelMessage(async (msg: ChannelMessage) => {
    try {
      await server.notification({
        method: "notifications/message",
        params: {
          level: "info",
          logger: `convene/${msg.topic}`,
          data: msg.content,
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

  if (!config.conveneApiKey) {
    process.stderr.write(
      "[channel-server] Error: CONVENE_API_KEY environment variable is required\n",
    );
    process.exit(1);
  }

  if (!config.conveneMeetingId) {
    process.stderr.write(
      "[channel-server] Error: CONVENE_MEETING_ID environment variable is required\n",
    );
    process.exit(1);
  }

  const { server, client } = createServer(config);

  // Connect the MCP transport (STDIO — Claude Code communicates via stdin/stdout)
  const transport = new StdioServerTransport();
  await server.connect(transport);

  process.stderr.write(
    `[channel-server] MCP server started (mode: ${config.agentMode})\n`,
  );

  // Connect to Convene AI after the MCP handshake so the server is ready to
  // receive tool calls even if the gateway connection is slow to establish.
  try {
    await client.connect();
    process.stderr.write(
      `[channel-server] Connected to meeting ${config.conveneMeetingId}\n`,
    );
  } catch (err) {
    // A failed Convene connection is logged but does not kill the MCP server.
    // Tools will return "not connected" errors; the operator can restart.
    process.stderr.write(
      `[channel-server] Warning: failed to connect to Convene — ${String(err)}\n`,
    );
  }

  // Graceful shutdown
  process.on("SIGINT", async () => {
    process.stderr.write("[channel-server] Shutting down...\n");
    await client.disconnect();
    process.exit(0);
  });

  process.on("SIGTERM", async () => {
    await client.disconnect();
    process.exit(0);
  });
}

// Only run main() when this file is the entry point (not when imported by tests).
// Bun sets import.meta.main = true for the directly executed file.
// The `main` property is Bun-specific; cast through unknown to avoid TS errors.
const isEntryPoint = (import.meta as unknown as { main?: boolean }).main ?? false;
if (isEntryPoint) {
  main().catch((err: unknown) => {
    process.stderr.write(`[channel-server] Fatal: ${String(err)}\n`);
    process.exit(1);
  });
}
