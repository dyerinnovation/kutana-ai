# CLI / MCP / Skill — Agent Integration Architecture

Three paths for agents to connect to and use Kutana AI:

## 1. Channel (Claude Code only)

Claude Code connects via the channel server (`services/channel-server/`), a stdio MCP subprocess that:
- Pushes real-time events (transcript, chat, tasks) into the conversation
- Provides 18+ MCP tools natively
- Handles auth automatically via API key in env vars

No skill needed — the channel provides tools + context natively.

## 2. CLI (`services/cli/`)

The `kutana` CLI is a Python command-line tool (installed via `pip install kutana-ai`) that wraps the Kutana API. Any agent with Bash access can use it.

- JSON output by default — agents parse structured data
- Session state in `~/.kutana/` — join once, subsequent commands reuse session
- Single URL config — `kutana auth login --url URL --api-key KEY`
- `kutana mcp` subcommand starts a stdio MCP server for MCP-native clients

### Why CLI over MCP?
- Context-efficient — CLI output is compact JSON, MCP tool definitions consume 40%+ of context
- Composable — pipe, chain, and script commands
- Universal — any agent with shell access can use it
- Follows industry best practice (OpenClaw recommends CLI-first)

## 3. MCP Server (`services/mcp-server/`)

For agents in MCP-native environments (Claude Desktop, VS Code Copilot) that can't use Bash:
- Remote HTTP MCP server at `https://<domain>/mcp`
- 27 `kutana_*` tools with typed parameters
- Bearer token auth (API key → JWT exchange)
- Also accessible via `kutana mcp` CLI subcommand (stdio mode)

## 4. Skill

Skills teach agents HOW to use Kutana in meetings — workflows, not setup.

- **Location:** `integrations/openclaw-plugin/skills/kutana/SKILL.md`
- **Distribution:** ClawHub (OpenClaw registry) + manual install
- **Pattern:** CLI-first — teaches Bash commands, with MCP as fallback
- **Reference:** Google Workspace CLI skills (gog-calendar, gog-email-triage)

## Integration Matrix

| Feature | Channel (Claude Code) | CLI | MCP Server |
|---------|----------------------|-----|------------|
| Real-time events | Yes (push) | No (poll) | No (poll) |
| Context efficiency | Medium (MCP tools) | High (JSON output) | Low (tool defs) |
| Composability | No | Yes (pipe/script) | No |
| Install | claude mcp add-json | pip install kutana-ai | Config URL + key |
| Skill needed | No | Yes (teaches workflows) | Optional |

## Key Files
- CLI: `services/cli/src/cli/main.py`
- Channel: `services/channel-server/src/server.ts`
- MCP: `services/mcp-server/src/mcp_server/main.py`
- Skill: `integrations/openclaw-plugin/skills/kutana/SKILL.md`
- Plugin: `integrations/openclaw-plugin/openclaw.plugin.json`
