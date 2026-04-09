# Managed Agents — Anthropic Integration Pattern

## Overview

Kutana managed agents are pre-built AI agents that users activate from the dashboard. Under the hood, each managed agent runs as an Anthropic hosted session connected to the Kutana MCP server. The Anthropic API handles model inference, tool execution, and session state — Kutana provides the meeting tools and meeting context.

## Architecture

```
User activates template
        │
        ▼
┌──────────────────────────┐
│  Kutana API Server       │
│  (activation endpoint)   │
│                          │
│  1. Fetch template       │
│  2. Prepend SOPs (Biz)   │
│  3. Register agent       │
│  4. Create vault (JWT)   │
│  5. Start session        │
│  6. Store session ID     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Anthropic Beta API      │
│                          │
│  • Agent definition      │
│  • Session lifecycle     │
│  • MCP tool routing      │
│  • SSE event stream      │
└──────────┬───────────────┘
           │ MCP tool calls
           ▼
┌──────────────────────────┐
│  Kutana MCP Server       │
│                          │
│  • kutana_* tools        │
│  • JWT auth (vault)      │
│  • Meeting context       │
└──────────────────────────┘
```

## Key Components

### Agent Registration (`managed_agents.register_agents`)

Creates Anthropic agent definitions from Kutana templates. Each agent is configured with:
- **Model:** `claude-sonnet-4-6` (default)
- **System prompt:** From `AgentTemplateORM.system_prompt` (with optional SOP prepend)
- **MCP server:** `https://api-dev.kutana.ai/mcp/` (Kutana's production MCP endpoint)
- **Tools:** Full `kutana_*` MCP toolset

Agent definitions are idempotent — re-registering the same template creates a new agent ID.

### Vault (`managed_agents.create_vault`)

Stores MCP authentication credentials (JWT) that the Anthropic session uses to authenticate with the Kutana MCP server. The vault is created per-activation and scoped to the user's agent permissions.

### Session Lifecycle (`managed_agents.start_session` / `end_session`)

- **Start:** Creates an Anthropic session bound to an agent + environment + vault. Returns a session ID stored in `HostedAgentSessionORM.anthropic_session_id`.
- **Events:** The session processes meeting events via `send_message()`. The Anthropic model reads the transcript, uses `kutana_*` tools, and posts output to meeting chat.
- **Stream:** `stream_events()` yields SSE events from the session — used to relay agent activity to the frontend.
- **End:** Sends a `user.interrupt` event to gracefully terminate the session.

### Organization SOPs

Business-tier templates include a `[ORGANIZATION SOP BLOCK]` marker in their system prompt. At activation:

1. Query `organization_sops` for the org + template category
2. Replace the marker with SOP content
3. Pass the combined prompt to `register_agents()`

## Data Model

### `agent_templates` (existing, extended)
- `tier` (string): `basic`, `pro`, or `business` — controls activation access
- `system_prompt` (text): Full prompt loaded into the Anthropic agent definition

### `hosted_agent_sessions` (existing, extended)
- `anthropic_session_id` (string): Anthropic session ID for the active session
- `anthropic_agent_id` (string): Anthropic agent definition ID

### `organization_sops` (new)
- `organization_id` (UUID): FK to organization
- `name` (string): SOP name
- `category` (string): Matches template category (engineering, research, hr, etc.)
- `content` (text): SOP content prepended to system prompt

## Security

- Anthropic API key is stored as an environment variable (`ANTHROPIC_API_KEY`), never in the database
- MCP authentication uses per-activation JWTs stored in Anthropic vaults — scoped to the user's agent permissions
- Scope enforcement on the MCP server ensures agents can only use tools their scope allows
- Rate limiting applies to managed agents the same as custom agents

## Files

| File | Purpose |
|------|---------|
| `services/api-server/src/api_server/managed_agents.py` | Anthropic API wrapper (register, session, vault) |
| `services/api-server/src/api_server/routes/agent_templates.py` | Activation endpoint with tier enforcement |
| `packages/kutana-core/src/kutana_core/database/models.py` | ORM models (AgentTemplateORM, HostedAgentSessionORM, OrganizationSOP) |
| `alembic/versions/j2b3c4d5e6f7_managed_agents_schema.py` | Migration: tier column, session fields, SOP table, 10 templates |
| `internal-docs/development/managed-agent-system-prompts.md` | All 10 system prompts |
| `internal-docs/development/managed-agent-tiers.md` | Tier assignments and enforcement details |
