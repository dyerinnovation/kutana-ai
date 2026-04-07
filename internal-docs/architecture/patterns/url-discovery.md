# URL Discovery Pattern

## Problem

Kutana clients (CLI, MCP server, OpenClaw plugin, channel server) need multiple URLs to operate:

- **API base URL** — REST endpoints for auth, meetings, tasks, etc.
- **WebSocket URL** — agent-gateway for real-time meeting participation

Requiring users to configure each URL separately is error-prone and creates friction, especially across deployment topologies (managed cloud with subdomains, on-prem single-server with path-based routing, local dev).

## Solution

A single base URL + a well-known discovery endpoint:

```
GET {base_url}/.well-known/kutana.json
```

Clients configure **one URL**. On startup, they fetch the discovery document to resolve all service endpoints.

### Discovery Response Schema

```json
{
  "api": "https://api.kutana.ai/v1",
  "ws": "wss://ws.kutana.ai",
  "version": "v1"
}
```

| Field     | Type   | Description                              |
|-----------|--------|------------------------------------------|
| `api`     | string | Base URL for REST API (includes version) |
| `ws`      | string | WebSocket URL for agent-gateway          |
| `version` | string | API version string                       |

The file is static — served from `web/public/.well-known/kutana.json` by the web frontend. No backend logic required.

## SDK Startup Flow

Clients resolve endpoints using a 4-tier fallback chain:

```
1. Explicit env vars     →  KUTANA_API_URL / KUTANA_WS_URL (always wins)
2. Discovery             →  fetch {base_url}/.well-known/kutana.json
3. Convention fallback   →  derive from base_url (api.{host}, ws.{host})
4. Local defaults        →  https://kutana.spark-b0f2.local/api/v1
```

**Priority:** Explicit > Discovery > Convention > Defaults.

If discovery fails (network error, 404), the client falls back silently to convention-based URL derivation. This keeps the system resilient — discovery enhances but is never required.

### Client behavior

1. Check for `KUTANA_API_URL` / `KUTANA_WS_URL` env vars. If set, use them directly.
2. Fetch `{base_url}/.well-known/kutana.json`.
3. On success: cache the response (CLI caches to `~/.kutana/discovery.json`).
4. On failure: derive URLs from the base URL using subdomain conventions.
5. Final fallback: hardcoded local defaults for dev environments.

## Deployment Examples

### Managed service (subdomains)

Users configure: `https://kutana.ai`

Discovery returns:
```json
{
  "api": "https://api.kutana.ai/v1",
  "ws": "wss://ws.kutana.ai",
  "version": "v1"
}
```

Each service has its own subdomain. TLS terminates at the edge (Cloudflare). Clean URLs, no path prefixes needed.

### On-prem single server (path-based)

Users configure: `https://meetings.corp.example.com`

Discovery returns:
```json
{
  "api": "https://meetings.corp.example.com/v1",
  "ws": "wss://meetings.corp.example.com/ws",
  "version": "v1"
}
```

All services behind a single host. Nginx/ingress routes by path prefix (`/v1` → api-server, `/ws` → agent-gateway). The `/v1` route passes through directly to the API server.

### Dev environment (current setup)

Users configure: `https://kutana.spark-b0f2.local`

Discovery returns:
```json
{
  "api": "https://kutana.spark-b0f2.local/v1",
  "ws": "wss://kutana.spark-b0f2.local/ws",
  "version": "v1"
}
```

K3s ingress handles path-based routing. Both `/api/v1/...` (legacy) and `/v1/...` (new) resolve to the API server. The legacy `/api` prefix is maintained for backwards compatibility during migration.

## Ingress Routing

The internal K8s ingress supports both legacy and new paths:

| Path pattern       | Target      | Ingress resource | Notes                                    |
|--------------------|-------------|------------------|------------------------------------------|
| `/api(/\|$)(.*)`   | api-server  | main (rewrite)   | Legacy — rewrites to strip `/api` prefix |
| `/v1`              | api-server  | `-v1` (no rewrite) | New — passes path through directly     |
| `/ws(/\|$)(.*)`    | agent-gw    | `-ws` (rewrite)  | WebSocket connections                    |
| `/`                | web         | `-web` (no rewrite) | Frontend catch-all                    |

The `/v1` route uses a **separate Ingress resource** (`kutana-v1`) with no `rewrite-target` annotation. This is necessary because the main internal ingress uses `rewrite-target: /$2` to strip path prefixes — but the API server mounts routes at `/v1/...`, so the `/v1` prefix must be preserved.

The public API subdomain (`api-dev.kutana.ai`) routes `/` directly to api-server with no rewrite — clients hit `/v1/...` paths natively.

## Precedent

This pattern is well-established in collaboration platforms:

- **Slack** — `apps.connections.open` returns a WebSocket URL for Socket Mode apps. Clients configure one OAuth token; the API tells them where to connect.
- **Discord** — `GET /gateway` (or `/gateway/bot`) returns `{"url": "wss://gateway.discord.gg"}`. Bots discover the WebSocket endpoint at runtime.
- **Matrix** — `GET /.well-known/matrix/client` returns `{"m.homeserver": {"base_url": "https://matrix.example.com"}}`. Federation and client discovery both use well-known files.

Kutana follows the Matrix model most closely: a static well-known file that maps a single domain to all required service endpoints.
