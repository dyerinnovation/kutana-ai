# Managed Agents Rules

Kutana uses Anthropic's Claude Managed Agents platform (beta) to run the 10 template agents.

## CRITICAL: Always verify against local docs

The Managed Agents API is new (beta). Your training data may not include it or may be wrong. Before writing or modifying ANY managed agent code:

1. **Read the local docs first:** `internal-docs/reference/anthropic-managed-agents/`
2. **Never assume SDK capabilities** — check what `client.beta` actually exposes in the installed version
3. **Never assume API shapes** — the beta may have changed since your training cutoff
4. **If the SDK doesn't have it, use raw HTTP** with the beta header or the `ant` CLI
5. **The `ant` CLI is installed** — use it for quick validation (`ant beta:agents list`, etc.)

This rule exists because agents previously wrote code against `client.beta.agents` without checking that the API existed in the installed SDK version, wasting multiple sessions.

## Use context7 for SDK lookups

The context7 MCP tool (`resolve-library-id` → `query-docs`) has up-to-date documentation for the `anthropic` SDK, `langfuse` SDK, and other dependencies. **Always use context7 first** when working with these libraries — it's faster and more accurate than guessing or web-fetching. Examples:

```
resolve-library-id("anthropic python sdk") → query-docs(library_id, "managed agents beta")
resolve-library-id("langfuse python") → query-docs(library_id, "traces generations scores")
```

Do NOT write code against SDK APIs from memory — query context7 to confirm the API surface exists in the current version.

## Beta Header

All Managed Agents API requests require the `managed-agents-2026-04-01` beta header. The Python/TS SDKs set this automatically via `client.beta.*` methods.

## SDK Version

Requires `anthropic >= 0.92.0`. The SDK is available in the api-server uv workspace. Bumped from 0.84.0 on 2026-04-09 — the managed agents beta API was not in 0.84.0.

## API Endpoints

- `POST /v1/agents` — create agent
- `POST /v1/environments` — create environment
- `POST /v1/sessions` — create session
- `POST /v1/sessions/{id}/events` — send events
- `GET /v1/sessions/{id}/stream` — SSE stream

## CLI (`ant`)

The Anthropic CLI is called `ant` (not `anthropic`). Install via `brew install anthropics/tap/ant`.

Key commands:
```bash
ant beta:agents create --name "..." --model '{id: claude-sonnet-4-6}' --system "..." --tool '{type: agent_toolset_20260401}'
ant beta:agents list
ant beta:environments create --name "..." --config '{type: cloud, networking: {type: unrestricted}}'
ant beta:sessions create --agent "$AGENT_ID" --environment "$ENVIRONMENT_ID"
ant beta:sessions list
ant beta:sessions:events send --session-id "$SESSION_ID"
```

## Reference Documentation

Local copies of the Anthropic managed agents docs are at:
`internal-docs/reference/anthropic-managed-agents/`

Always read these docs before writing or modifying managed agent code. The API is new and may not match training data.

### Key files:
- `internal-docs/reference/anthropic-managed-agents/overview.md` — concepts (agents, environments, sessions, events)
- `internal-docs/reference/anthropic-managed-agents/quickstart.md` — setup steps and code examples
- `internal-docs/reference/anthropic-managed-agents/agent-setup.md` — agent configuration, versioning, lifecycle
- `internal-docs/reference/anthropic-managed-agents/environments.md` — container config, packages, networking
- `internal-docs/reference/anthropic-managed-agents/sessions.md` — session creation, statuses, operations
- `internal-docs/reference/anthropic-managed-agents/events-and-streaming.md` — event types, streaming, interrupts
- `internal-docs/reference/anthropic-managed-agents/tools.md` — built-in tools, custom tools, configuration
- `services/api-server/src/api_server/managed_agents.py` — Kutana's managed agent wrapper
- `services/api-server/src/api_server/agent_lifecycle.py` — meeting event → agent session wiring
- `internal-docs/development/managed-agent-system-prompts.md` — system prompts for all 10 agents

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | Versioned config: model + system prompt + tools + MCP servers + skills |
| **Environment** | Container template: packages, networking rules |
| **Session** | Running agent instance in an environment |
| **Events** | Messages between your app and the agent (SSE) |

## Tool Type

Use `{"type": "agent_toolset_20260401"}` to enable all built-in tools (bash, read, write, edit, glob, grep, web_fetch, web_search).

## Agent Templates (by tier):
- **Basic:** Meeting Notetaker, Meeting Summarizer
- **Pro:** + Action Item Tracker, Decision Logger, Standup Facilitator, Code Discussion Tracker
- **Business:** + Sprint Retro Coach, Sprint Planner, User Interviewer, Initial Interviewer

## Rate Limits

| Operation | Limit |
|-----------|-------|
| Create endpoints | 60 req/min |
| Read endpoints | 600 req/min |
