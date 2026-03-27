/**
 * Discord MCP HTTP Server
 *
 * Exposes Discord Bot API operations as MCP tools over Streamable HTTP transport.
 * Uses the Web Standard StreamableHTTPServerTransport which works natively with
 * Bun.serve's Request/Response API.
 *
 * Run with: bun src/index.ts
 *
 * Required environment variables:
 *   DISCORD_BOT_TOKEN — Discord bot token for authentication
 *
 * Optional:
 *   PORT — HTTP port to listen on (default: 3002)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { Client, GatewayIntentBits } from "discord.js";
import { registerTools } from "./tools.js";

const PORT = parseInt(process.env["PORT"] ?? "3002", 10);
const DISCORD_BOT_TOKEN = process.env["DISCORD_BOT_TOKEN"];

if (!DISCORD_BOT_TOKEN) {
  console.error(
    "[discord-mcp] Error: DISCORD_BOT_TOKEN environment variable is required",
  );
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Discord client
// ---------------------------------------------------------------------------

const discordClient = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

// ---------------------------------------------------------------------------
// MCP server factory — one server + transport per request (stateless mode)
// ---------------------------------------------------------------------------

function createMCPServer(): Server {
  const server = new Server(
    { name: "discord-mcp", version: "0.1.0" },
    {
      capabilities: { tools: {} },
    },
  );
  registerTools(server, discordClient);
  return server;
}

// ---------------------------------------------------------------------------
// HTTP server using Bun.serve with Web Standard StreamableHTTP transport
// ---------------------------------------------------------------------------

const httpServer = Bun.serve({
  port: PORT,
  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);

    // Health check endpoint
    if (url.pathname === "/health" && req.method === "GET") {
      return new Response(
        JSON.stringify({ status: "healthy", service: "discord-mcp" }),
        {
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    // MCP endpoint — handles POST (JSON-RPC), GET (SSE stream), DELETE (session close)
    if (url.pathname === "/mcp") {
      const transport = new WebStandardStreamableHTTPServerTransport();
      const mcpServer = createMCPServer();
      await mcpServer.connect(transport);
      return transport.handleRequest(req);
    }

    return new Response("Not Found", { status: 404 });
  },
});

// ---------------------------------------------------------------------------
// Start up
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  // Login to Discord
  await discordClient.login(DISCORD_BOT_TOKEN);
  console.log(
    `[discord-mcp] Discord bot logged in as ${discordClient.user?.tag}`,
  );
  console.log(
    `[discord-mcp] MCP HTTP server listening on port ${httpServer.port}`,
  );
  console.log(
    `[discord-mcp] Health: http://localhost:${httpServer.port}/health`,
  );
  console.log(
    `[discord-mcp] MCP endpoint: http://localhost:${httpServer.port}/mcp`,
  );
}

main().catch((err: unknown) => {
  console.error(`[discord-mcp] Fatal: ${String(err)}`);
  process.exit(1);
});

// Graceful shutdown
process.on("SIGINT", async () => {
  console.log("[discord-mcp] Shutting down...");
  discordClient.destroy();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  discordClient.destroy();
  process.exit(0);
});
