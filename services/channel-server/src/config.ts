/**
 * Configuration for the Convene AI Channel Server.
 *
 * All settings are read from environment variables so the server can be
 * parameterised without code changes.
 */

import type { AgentMode, EntityType } from "./types.js";

export interface ChannelServerConfig {
  /** WebSocket URL of the Convene agent gateway (e.g. wss://convene.spark-b0f2.local/ws). */
  conveneApiUrl: string;
  /** HTTP base URL of the Convene API server. */
  conveneHttpUrl: string;
  /** Agent API key used for authentication. */
  conveneApiKey: string;
  /**
   * Optional pre-issued gateway JWT.  When set, the API-key → JWT exchange
   * step is skipped and this token is used directly.
   */
  conveneBearerToken: string;
  /** Display name shown in the meeting participant list (default: "Claude Code"). */
  conveneAgentName: string;
  /** Controls which event types are forwarded to Claude. */
  agentMode: AgentMode;
  /** Entity types to forward when agentMode is "selective". */
  entityFilter: EntityType[];
  /** Whether to reject unauthorized TLS certificates. Set false for self-signed certs. */
  tlsRejectUnauthorized: boolean;
}

/**
 * Load configuration from environment variables.
 *
 * Logs a warning and applies defaults for optional variables.
 * Callers should validate that required fields (conveneApiKey)
 * are non-empty before starting the server.
 */
export function loadConfig(): ChannelServerConfig {
  const rawApiUrl = process.env["CONVENE_API_URL"] ?? "ws://localhost:8003";

  // Derive HTTP URL: prefer explicit override, otherwise convert ws:// → http://
  const rawHttpUrl =
    process.env["CONVENE_HTTP_URL"] ?? deriveHttpUrl(rawApiUrl);

  const rawMode = process.env["CONVENE_AGENT_MODE"] ?? "both";
  const agentMode = parseAgentMode(rawMode);

  const rawFilter = process.env["CONVENE_ENTITY_FILTER"] ?? "";
  const entityFilter = parseEntityFilter(rawFilter);

  const rawTls = process.env["CONVENE_TLS_REJECT_UNAUTHORIZED"] ?? "0";
  const tlsRejectUnauthorized = rawTls !== "0";

  return {
    conveneApiUrl: rawApiUrl,
    conveneHttpUrl: rawHttpUrl,
    conveneApiKey: process.env["CONVENE_API_KEY"] ?? "",
    conveneBearerToken: process.env["CONVENE_BEARER_TOKEN"] ?? "",
    conveneAgentName: process.env["CONVENE_AGENT_NAME"] ?? "Claude Code",
    agentMode,
    entityFilter,
    tlsRejectUnauthorized,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function deriveHttpUrl(wsUrl: string): string {
  // ws://host:port → http://host:port
  // wss://host:port → https://host:port
  // Common port mapping: agent gateway :8003 → API server :8000
  return wsUrl
    .replace(/^wss:\/\//, "https://")
    .replace(/^ws:\/\//, "http://")
    .replace(/:8003\b/, ":8000");
}

function parseAgentMode(raw: string): AgentMode {
  const valid: readonly AgentMode[] = [
    "transcript",
    "insights",
    "both",
    "selective",
  ];
  if ((valid as readonly string[]).includes(raw)) {
    return raw as AgentMode;
  }
  process.stderr.write(
    `[channel-server] Unknown CONVENE_AGENT_MODE "${raw}", defaulting to "both"\n`,
  );
  return "both";
}

function parseEntityFilter(raw: string): EntityType[] {
  if (!raw.trim()) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean) as EntityType[];
}
