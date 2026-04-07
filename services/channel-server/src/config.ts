/**
 * Configuration for the Kutana AI Channel Server.
 *
 * All settings are read from environment variables so the server can be
 * parameterised without code changes.
 */

import type { AgentMode, EntityType } from "./types.js";

export interface ChannelServerConfig {
  /** WebSocket URL of the Kutana agent gateway (e.g. wss://kutana.spark-b0f2.local/ws). */
  kutanaApiUrl: string;
  /** HTTP base URL of the Kutana API server. */
  kutanaHttpUrl: string;
  /** Agent API key used for authentication. */
  kutanaApiKey: string;
  /**
   * Optional pre-issued gateway JWT.  When set, the API-key → JWT exchange
   * step is skipped and this token is used directly.
   */
  kutanaBearerToken: string;
  /** Display name shown in the meeting participant list (default: "Claude Code"). */
  kutanaAgentName: string;
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
 * Callers should validate that required fields (kutanaApiKey)
 * are non-empty before starting the server.
 */
export function loadConfig(): ChannelServerConfig {
  const rawBaseUrl = process.env["KUTANA_URL"] ?? "";
  const rawApiUrl =
    process.env["KUTANA_API_URL"] ??
    (rawBaseUrl ? deriveWsUrl(rawBaseUrl) : "ws://localhost:8003");

  // Derive HTTP URL: KUTANA_HTTP_URL > KUTANA_URL > derived from WS URL
  const rawHttpUrl =
    process.env["KUTANA_HTTP_URL"] ?? (rawBaseUrl || deriveHttpUrl(rawApiUrl));

  const rawMode = process.env["KUTANA_AGENT_MODE"] ?? "both";
  const agentMode = parseAgentMode(rawMode);

  const rawFilter = process.env["KUTANA_ENTITY_FILTER"] ?? "";
  const entityFilter = parseEntityFilter(rawFilter);

  const rawTls = process.env["KUTANA_TLS_REJECT_UNAUTHORIZED"] ?? "0";
  const tlsRejectUnauthorized = rawTls !== "0";

  return {
    kutanaApiUrl: rawApiUrl,
    kutanaHttpUrl: rawHttpUrl,
    kutanaApiKey: process.env["KUTANA_API_KEY"] ?? "",
    kutanaBearerToken: process.env["KUTANA_BEARER_TOKEN"] ?? "",
    kutanaAgentName: process.env["KUTANA_AGENT_NAME"] ?? "Claude Code",
    agentMode,
    entityFilter,
    tlsRejectUnauthorized,
  };
}

// ---------------------------------------------------------------------------
// Endpoint discovery
// ---------------------------------------------------------------------------

interface DiscoveredEndpoints {
  api: string;
  ws: string;
}

/**
 * Fetch endpoint URLs from a well-known discovery document.
 *
 * Tries `{baseUrl}/.well-known/kutana.json` first; on failure falls back
 * to a convention-based derivation (prepend `api.` / `ws.` to the domain).
 */
async function discoverEndpoints(
  baseUrl: string,
): Promise<DiscoveredEndpoints> {
  const discoveryUrl = `${baseUrl.replace(/\/+$/, "")}/.well-known/kutana.json`;

  try {
    const resp = await fetch(discoveryUrl, {
      signal: AbortSignal.timeout(5_000),
    });

    if (resp.ok) {
      const data = (await resp.json()) as DiscoveredEndpoints;
      process.stderr.write(
        `[channel-server] Discovery: api=${data.api}, ws=${data.ws}\n`,
      );
      return data;
    }

    process.stderr.write(
      `[channel-server] Discovery failed (${resp.status.toString()}), using convention fallback\n`,
    );
  } catch (err) {
    process.stderr.write(
      `[channel-server] Discovery fetch error: ${String(err)}, using convention fallback\n`,
    );
  }

  // Convention fallback: prepend api./ws. to the domain
  return conventionFallback(baseUrl);
}

/** Derive API and WS URLs by prepending `api.` / `ws.` to the domain. */
function conventionFallback(baseUrl: string): DiscoveredEndpoints {
  const url = new URL(baseUrl);
  const apiScheme = url.protocol; // "https:" or "http:"
  const wsScheme = url.protocol === "https:" ? "wss:" : "ws:";

  const api = `${apiScheme}//api.${url.host}`;
  const ws = `${wsScheme}//ws.${url.host}`;

  process.stderr.write(
    `[channel-server] Convention fallback: api=${api}, ws=${ws}\n`,
  );
  return { api, ws };
}

/**
 * Resolve final endpoint URLs via discovery.
 *
 * Call this after `loadConfig()` but before authenticating.
 * Mutates the config in place.
 *
 * **Precedence:**
 * 1. Explicit env vars (`KUTANA_HTTP_URL`, `KUTANA_API_URL`) — highest, skip discovery
 * 2. Discovery from `{KUTANA_URL}/.well-known/kutana.json`
 * 3. Convention fallback (prepend `api.`/`ws.` to domain)
 * 4. Local defaults (`http://localhost:8000`, `ws://localhost:8003`) — already set by loadConfig
 */
export async function resolveEndpoints(
  config: ChannelServerConfig,
): Promise<void> {
  const hasExplicitHttp = !!process.env["KUTANA_HTTP_URL"];
  const hasExplicitWs = !!process.env["KUTANA_API_URL"];
  const baseUrl = process.env["KUTANA_URL"] ?? "";

  // If both explicit URLs are set, skip discovery entirely
  if (hasExplicitHttp && hasExplicitWs) {
    process.stderr.write(
      "[channel-server] Explicit KUTANA_HTTP_URL and KUTANA_API_URL set, skipping discovery\n",
    );
    return;
  }

  // No base URL to discover from — keep loadConfig defaults
  if (!baseUrl) {
    return;
  }

  const endpoints = await discoverEndpoints(baseUrl);

  if (!hasExplicitHttp) {
    config.kutanaHttpUrl = endpoints.api;
  }
  if (!hasExplicitWs) {
    config.kutanaApiUrl = endpoints.ws;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function deriveWsUrl(httpUrl: string): string {
  return (
    httpUrl
      .replace(/^https:\/\//, "wss://")
      .replace(/^http:\/\//, "ws://") + "/ws"
  );
}

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
    `[channel-server] Unknown KUTANA_AGENT_MODE "${raw}", defaulting to "both"\n`,
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
