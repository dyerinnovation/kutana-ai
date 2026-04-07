# Feed OAuth Integration Plan

Replace the manual MCP URL + auth token entry in the Create Feed modal with an OAuth-based connection flow, starting with Slack.

## Current State

The Create Feed modal (`web/src/pages/FeedsPage.tsx`, lines 522-543) shows two raw text fields when `delivery_type === "mcp"`:

- **MCP Server URL** — user pastes a URL like `https://mcp.example.com/sse`
- **Auth Token** — user pastes a bearer token

The backend (`services/api-server/src/api_server/routes/feeds.py`) stores the URL on the `FeedORM` row and encrypts the token into `FeedSecretORM`. At execution time, `feed_runner.py` decrypts the token and passes it to `build_adapter()`, which creates an `MCPChannelAdapter(server_url, auth_token, platform)`. The feed agent then connects to the external MCP server using that URL + token for JSON-RPC tool calls.

**Problem:** Users should not be sourcing MCP server URLs and bearer tokens themselves. For Slack specifically, the correct UX is "click Connect Slack, authorize in Slack, done."

## Proposed Architecture

### Key Insight: Eliminate the External MCP Server for Slack

The current design assumes the user runs or has access to a third-party Slack MCP server. With OAuth, Kutana owns the Slack connection directly. Instead of routing through an external MCP server, the feed agent can either:

1. **Option A — Hosted MCP server:** Kutana runs the `@modelcontextprotocol/server-slack` package as a stdio subprocess (like Discord's `ClaudeCodeChannelAdapter` already does), injecting the stored bot token via env vars. No external MCP URL needed.
2. **Option B — Direct Slack API adapter:** Create a `SlackAPIAdapter` that calls the Slack Web API directly (via `slack-sdk`) instead of going through MCP at all. Simpler, fewer moving parts.

**Recommendation: Option A (stdio MCP subprocess).** It matches the existing `ClaudeCodeChannelAdapter` pattern, reuses the feed agent's MCP tool-use loop, and gives the agent access to the full Slack MCP toolset without custom API wrappers.

This means Slack feeds shift from `delivery_type: "mcp"` to `delivery_type: "channel"` internally — the same pattern Discord already uses.

## Slack OAuth 2.0 Flow (Step by Step)

### Prerequisites

1. Create a Slack App at https://api.slack.com/apps with the following bot token scopes:
   - `channels:history` — read messages in public channels
   - `channels:read` — list channels
   - `chat:write` — post messages
   - `reactions:write` — add emoji reactions
   - `users:read` — view users
   - `users.profile:read` — view user profiles
2. Configure the app's OAuth redirect URL to `https://dev.kutana.ai/api/v1/integrations/slack/callback`
3. Store `SLACK_CLIENT_ID` and `SLACK_CLIENT_SECRET` as env vars on the api-server

### User-Facing Flow

```
User clicks "Connect Slack" button in Create Feed modal
  |
  v
Frontend redirects to: https://slack.com/oauth/v2/authorize
  ?client_id=KUTANA_SLACK_CLIENT_ID
  &scope=channels:history,channels:read,chat:write,reactions:write,users:read,users.profile:read
  &redirect_uri=https://dev.kutana.ai/api/v1/integrations/slack/callback
  &state=<signed JWT with user_id + feed_draft_id + CSRF nonce>
  |
  v
User approves in Slack's consent screen
  |
  v
Slack redirects to callback URL with ?code=TEMP_CODE&state=STATE
  |
  v
Backend exchanges code for bot token via oauth.v2.access
  |
  v
Backend stores encrypted bot token + team metadata
  |
  v
Frontend receives success redirect, feed is auto-configured
```

### oauth.v2.access Response (What We Store)

```json
{
  "ok": true,
  "access_token": "xoxb-...",
  "token_type": "bot",
  "scope": "channels:history,channels:read,chat:write,...",
  "bot_user_id": "U0KRQLJ9H",
  "app_id": "A0KRD7HC3",
  "team": { "name": "Acme Corp", "id": "T9TK3CUKW" },
  "authed_user": { "id": "U1234" }
}
```

Store: `access_token` (encrypted in `FeedSecretORM`), `team.id`, `team.name`, `bot_user_id`, `scope`.

## Backend Changes

### 1. New Router: `routes/integrations.py`

```
POST /api/v1/integrations/slack/connect
  - Requires auth (CurrentUser)
  - Generates signed state JWT (user_id, optional feed_draft_id, CSRF nonce)
  - Returns { authorize_url: "https://slack.com/oauth/v2/authorize?..." }

GET /api/v1/integrations/slack/callback
  - Receives ?code=...&state=...
  - Validates state JWT signature + expiry
  - Calls Slack oauth.v2.access to exchange code for bot token
  - Encrypts and stores token in FeedSecretORM (or new IntegrationORM)
  - Stores team_id, team_name, bot_user_id, granted scopes
  - Redirects browser to frontend success URL with integration_id
```

### 2. New Database Model: `IntegrationORM`

Decouple the OAuth connection from a specific feed so one Slack workspace connection can serve multiple feeds:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK -> users |
| provider | str | "slack" |
| team_id | str | Slack workspace ID (T...) |
| team_name | str | Display name |
| bot_user_id | str | Bot's Slack user ID |
| scopes | str | Comma-separated granted scopes |
| encrypted_token | text | AES-256-GCM encrypted xoxb- token |
| token_hint | str(8) | Last 4 chars |
| is_active | bool | Default true |
| created_at | datetime | |
| revoked_at | datetime | Null until disconnected |

Add a nullable `integration_id` FK column to `FeedORM` that links a feed to its OAuth integration.

### 3. Feed Creation Changes

- `FeedCreate` model: add optional `integration_id: UUID | None`
- When creating a Slack feed with `integration_id`, the backend:
  - Looks up the `IntegrationORM` to get the encrypted bot token
  - Sets `delivery_type = "channel"` (not "mcp")
  - No longer requires `mcp_server_url` or `mcp_auth_token`
- `build_adapter()` in `adapters.py`: when platform is "slack" and an integration exists, use the `ClaudeCodeChannelAdapter` pattern with the `@modelcontextprotocol/server-slack` package

### 4. Adapter Registry Update

Change Slack from `MCPChannelAdapter` to a new `SlackOAuthAdapter` (subclass of `ClaudeCodeChannelAdapter`):

```python
class SlackOAuthAdapter(ChannelAdapter):
    """Slack adapter using OAuth bot token + stdio MCP subprocess."""

    def __init__(self, bot_token: str, team_id: str, channel_ids: str = "") -> None:
        self._bot_token = bot_token
        self._team_id = team_id
        self._channel_ids = channel_ids

    def mcp_servers(self) -> list[MCPServerConfig | StdioMCPServerConfig]:
        return [
            StdioMCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-slack"],
                env={
                    "SLACK_BOT_TOKEN": self._bot_token,
                    "SLACK_TEAM_ID": self._team_id,
                    "SLACK_CHANNEL_IDS": self._channel_ids,
                },
            )
        ]
```

Update `ADAPTER_REGISTRY` to map `"slack"` to `SlackOAuthAdapter`.

## Frontend Changes

### 1. Replace MCP Fields with "Connect Slack" Button

In the Create Feed modal, when `platform === "slack"`:

- **Before:** Show MCP Server URL + Auth Token inputs
- **After:** Show one of:
  - **No integration:** "Connect Slack" button that calls `POST /integrations/slack/connect`, then redirects the browser to the returned `authorize_url`
  - **Integration exists:** Green checkmark with "Connected to [Team Name]" + "Disconnect" link

### 2. OAuth Callback Landing Page

Add a route at `/integrations/slack/callback` (or handle via the api-server redirect):

- Parse `integration_id` from the redirect URL params
- Show success state ("Slack connected!")
- Auto-navigate back to the Create Feed modal with the integration pre-selected

### 3. Channel Selector

Once connected, replace the free-text channel input with a dropdown that lists channels from the connected workspace (fetched via a new `GET /integrations/{id}/channels` endpoint that calls `conversations.list` through the stored bot token).

### 4. Feed Form State Changes

```typescript
// Old
const PLATFORM_DELIVERY: Record<string, "channel" | "mcp"> = {
  slack: "mcp",  // <- change this
  ...
};

// New
const PLATFORM_DELIVERY: Record<string, "channel" | "mcp"> = {
  slack: "channel",  // Now uses OAuth adapter
  ...
};
```

## How the Stored OAuth Token Connects to Feed Execution

Current flow (manual MCP):
```
FeedRunner -> decrypt FeedSecretORM.encrypted_token
           -> build_adapter(feed, token) -> MCPChannelAdapter(url, token)
           -> agent connects to external MCP server over HTTP
```

New flow (OAuth):
```
FeedRunner -> load IntegrationORM for feed.integration_id
           -> decrypt IntegrationORM.encrypted_token (xoxb- bot token)
           -> build_adapter(feed, token, team_id)
           -> SlackOAuthAdapter(bot_token, team_id)
           -> agent spawns @modelcontextprotocol/server-slack as stdio subprocess
           -> subprocess uses SLACK_BOT_TOKEN env var to call Slack APIs
           -> agent uses MCP tools (conversations_add_message, etc.) via stdio
```

The feed agent code (`feed_agent.py`) does not change — it already supports both HTTP and stdio MCP transports. The only change is in the adapter layer and token sourcing.

## Migration Path

1. Existing feeds with `delivery_type: "mcp"` and manual Slack tokens continue to work (backward compatible)
2. New Slack feeds use the OAuth flow and `delivery_type: "channel"`
3. Eventually deprecate manual MCP entry for Slack; show a migration banner for existing feeds

## Open Questions

1. **One integration per workspace or per user?** If two users connect the same Slack workspace, do they share one integration? Recommendation: one per user (simpler permissions), but store `team_id` to show "already connected" hints.

2. **Token rotation:** Slack supports optional token rotation (12-hour expiry + refresh tokens). Should we enable it? Pro: better security. Con: adds refresh logic to the feed runner. Recommendation: start without rotation, add it in a follow-up.

3. **Channel selection UX:** Should users pick a channel during feed creation, or should the feed agent auto-detect the right channel? Recommendation: explicit channel picker — users need to control where meeting data lands.

4. **Scoping for Enterprise Grid:** Enterprise Grid workspaces use `org.` scopes. Do we need to support this initially? Recommendation: defer — start with single-workspace installs.

5. **Uninstallation handling:** If a user uninstalls the Slack app from their workspace, the bot token is revoked. We need a `tokens_revoked` event handler or graceful error handling in the feed runner. Recommendation: handle token errors in feed_runner with a clear error message; add event subscription later.

6. **npx in production containers:** The `SlackOAuthAdapter` uses `npx -y @modelcontextprotocol/server-slack`. In the worker Docker image, we should pre-install this package rather than downloading at runtime. Add it to the worker Dockerfile.

7. **Discord parity:** Discord currently uses `ClaudeCodeChannelAdapter` which also needs a bot token (manually configured). Should we add Discord OAuth in parallel? Recommendation: do Slack first, then apply the same pattern to Discord.

## Implementation Order

1. Create Slack App in Slack API dashboard, configure scopes and redirect URL
2. Database migration: add `integrations` table, add `integration_id` FK to `feeds`
3. Backend: `routes/integrations.py` with connect + callback endpoints
4. Backend: `SlackOAuthAdapter` in `adapters.py`, update registry
5. Backend: update `feed_runner.py` to load integration tokens
6. Frontend: replace MCP fields with Connect Slack button + callback page
7. Frontend: channel picker dropdown
8. Worker Dockerfile: pre-install `@modelcontextprotocol/server-slack`
9. Test end-to-end: OAuth flow -> feed creation -> meeting trigger -> Slack delivery
10. Deprecation banner for existing manual-MCP Slack feeds
