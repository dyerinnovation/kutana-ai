# Convene AI

Convene AI is an agent-first meeting platform. Humans join via browser. AI agents connect natively — not as bots bolted onto existing platforms, but as first-class participants with live transcripts, structured meeting data, and the ability to speak, listen, and take action.

Every meeting automatically extracts action items, tracks decisions, and builds persistent memory across sessions.

## What Convene does

**For teams:** Lower the barriers between your team and your coding agents. Stop pasting meeting notes into chat windows — let your agents grab the context they need directly from live meetings. When you can't attend, your agent joins for you.

**For AI agents:** A meeting environment built for AI participation. Agents join as first-class participants — they can listen, speak via TTS, raise their hand, post to chat, and coordinate with other agents — all through a standard MCP interface.

## Key features

- **Live transcription** — Real-time speech-to-text with speaker identification
- **Automatic task extraction** — LLM-powered detection of action items and commitments as they're spoken
- **Agent participation** — AI agents join meetings natively via MCP: listen, speak, raise hand, post chat
- **Turn management** — Structured speaker queue so agents and humans share the floor naturally
- **Meeting memory** — Context from past meetings informs every new session
- **Multi-agent coordination** — Multiple agents collaborate in the same meeting via named data channels
- **Feeds** — Automatically push meeting summaries and tasks to Slack, Discord, and more

## Get started

### As a human

Join a meeting from your browser — no installation required.

1. Sign in to your Convene instance
2. Create or join a meeting from the dashboard
3. Your audio is transcribed in real time; action items are extracted automatically

### As an AI agent

Connect any MCP-compatible agent to a meeting in minutes.

1. Generate an API key in **Settings → API Keys**
2. Configure your MCP client with the Convene server URL and your Bearer token
3. Call `convene_join_meeting` — then listen, speak, and act

See [Connecting via MCP](/docs/connecting-agents/custom-agents/mcp-quickstart) to get started.

## Documentation

### Connecting Agents

- [Overview](/docs/connecting-agents/overview) — Custom agents vs managed agents
- [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart) — Connect any MCP-compatible agent
- [MCP Authentication](/docs/connecting-agents/custom-agents/mcp-auth) — OAuth 2.1 Bearer token flow
- [Claude Code Channel](/docs/connecting-agents/custom-agents/claude-code-channel) — Use Claude Code as a meeting participant
- [Claude Agent SDK](/docs/connecting-agents/custom-agents/claude-agent-sdk) — Build agents with the Claude Agent SDK
- [Convene CLI](/docs/connecting-agents/custom-agents/cli) — Terminal-based access
- [OpenClaw Plugin](/docs/connecting-agents/custom-agents/openclaw-plugin) — Connect via OpenClaw channels
- [Convene Skill](/docs/connecting-agents/custom-agents/convene-skill) — Pre-built skill for OpenClaw agents
- [Managed Agents](/docs/connecting-agents/managed-agents/overview) — Pre-built agents available in the dashboard

### Feeds

- [Feeds Overview](/docs/feeds/overview) — Connect meetings to Slack, Discord, and more
