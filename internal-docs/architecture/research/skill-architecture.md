# Kutana AI Skill Architecture

> Proposal for the `kutana-meeting` skill design.
> Based on research in `docs/research/openclaw-skills-research.md`.

---

## Overview

The `kutana-meeting` skill enables AI agents to participate in Kutana AI meetings as first-class participants. It wraps the Kutana MCP server tools in an OpenClaw-compatible skill package, making Kutana accessible to any agent framework (Claude Agent SDK, OpenClaw, generic LLM frameworks).

**Primary target:** OpenClaw agent ecosystem (ClawHub distribution)
**Secondary targets:** Claude Agent SDK, generic MCP-compatible frameworks

---

## Capability Mapping

The skill bundles four capability areas, each mapping to a group of MCP tools:

### 1. Meeting Lifecycle
*Join, leave, and monitor meeting state.*

| MCP Tool | Description |
|----------|-------------|
| `kutana_list_meetings` | Find available meetings to join |
| `kutana_join_meeting` | Connect to a meeting via the agent gateway |
| `kutana_leave_meeting` | Disconnect gracefully |
| `kutana_join_or_create_meeting` | Find active meeting by title or create new |
| `kutana_start_meeting` | Start a scheduled meeting |
| `kutana_end_meeting` | End an active meeting |
| `kutana_get_meeting_status` | Get comprehensive meeting state snapshot |

### 2. Turn Management
*Request the floor, check queue, signal when done.*

| MCP Tool | Description |
|----------|-------------|
| `kutana_raise_hand` | Request to speak (normal or urgent priority) |
| `kutana_get_queue_status` | See who's speaking and who's waiting |
| `kutana_get_speaking_status` | Check your current speaking status |
| `kutana_mark_finished_speaking` | Signal done, advance the queue |
| `kutana_cancel_hand_raise` | Withdraw from the speaker queue |

### 3. Chat
*Send and receive meeting chat messages.*

| MCP Tool | Description |
|----------|-------------|
| `kutana_send_chat_message` | Post a message to meeting chat |
| `kutana_get_chat_messages` | Read chat history with optional filters |

### 4. Context
*Access transcript and task information.*

| MCP Tool | Description |
|----------|-------------|
| `kutana_get_transcript` | Read recent transcript segments |
| `kutana_get_tasks` | Retrieve extracted tasks for a meeting |
| `kutana_create_task` | Create a new meeting task |
| `kutana_get_participants` | List current participants |
| `kutana_subscribe_channel` | Subscribe to a data channel |
| `kutana_publish_to_channel` | Publish to a data channel |

---

## Directory Layout

```
integrations/kutana-meeting-skill/
├── SKILL.md                  # OpenClaw skill definition (frontmatter + instructions)
├── README.md                 # Human-facing setup guide
├── scripts/
│   ├── connect.sh            # Helper to start the MCP server with correct env
│   └── mcp-bridge.py         # Generic Python MCP bridge for non-OpenClaw frameworks
└── examples/
    ├── meeting-assistant.md  # Example agent prompt using this skill
    └── note-taker.md         # Example note-taking agent
```

---

## SKILL.md Frontmatter

```yaml
---
name: kutana-meeting
version: 1.0.0
description: Join and participate in Kutana AI meetings — transcripts, chat, turn management, and task tracking
author: Dyer Innovation
category: productivity
tags:
  - meetings
  - transcription
  - collaboration
  - ai-agent
  - real-time
  - turn-taking
  - chat
capabilities:
  - meeting-lifecycle
  - turn-management
  - chat
  - context
requires:
  - env: KUTANA_API_KEY
    description: API key from your Kutana dashboard (Settings → API Keys)
  - env: KUTANA_API_URL
    description: Base URL of your Kutana API server (default: https://api.kutana.ai)
  - env: KUTANA_GATEWAY_WS_URL
    description: WebSocket URL for the agent gateway (default: ws://api.kutana.ai/gateway)
  - service: kutana-mcp-server
    description: Kutana MCP server must be running and reachable
mcp_compatible: true
mcp_server_url: "${KUTANA_MCP_URL:-http://localhost:3001/mcp}"
frameworks:
  - openclaw
  - claude-agent-sdk
  - generic
license: MIT
---
```

---

## SKILL.md Body Structure

The body follows a consistent structure that optimizes for agent comprehension:

```markdown
# Kutana Meeting Skill

You are participating in a Kutana AI meeting. Kutana is an agent-first meeting
platform where AI agents are first-class participants alongside humans.

## Quick Start

[3-5 sentence overview of what you can do in a meeting]

## Connection

[How to join/leave, what happens on connect, error handling]

## Turn Management

[When and how to raise hand, etiquette, when to mark finished]

## Chat

[How to send messages, what message types mean, when to use each]

## Context Access

[How to get transcripts, tasks, participants]

## Example: Full Meeting Participation

[End-to-end example showing join → listen → raise hand → speak → leave]

## Troubleshooting

[Common errors and how to resolve them]
```

---

## Connection Architecture

```
Claude Agent SDK / OpenClaw Agent
         │
         │  MCP protocol (Streamable HTTP)
         ▼
kutana-mcp-server (FastMCP, port 3001)
         │
         ├── REST API calls ──────► api-server (port 8000)
         │                               │
         │                               ▼
         │                          PostgreSQL
         │
         └── WebSocket ──────────► agent-gateway (port 8003)
                                        │
                                        ├── Redis Streams (events)
                                        ├── TurnManager (speaker queue)
                                        └── ChatStore (chat messages)
```

### Authentication Flow

1. Agent starts with `KUTANA_API_KEY` in environment
2. MCP server exchanges API key for short-lived JWT via `POST /token/mcp`
3. JWT is validated on every MCP tool call
4. For gateway operations, a separate gateway JWT is exchanged via `POST /token/gateway`
5. Gateway JWT is used for the WebSocket connection

### connect.sh Helper

```bash
#!/usr/bin/env bash
# Start the Kutana MCP server with your API key configured.
# Usage: ./connect.sh

set -euo pipefail

: "${KUTANA_API_KEY:?KUTANA_API_KEY must be set}"
: "${KUTANA_API_URL:=http://localhost:8000}"
: "${KUTANA_GATEWAY_WS_URL:=ws://localhost:8003}"
: "${KUTANA_MCP_PORT:=3001}"

docker run --rm -d \
  --name kutana-mcp \
  -p "${KUTANA_MCP_PORT}:3001" \
  -e MCP_API_KEY="${KUTANA_API_KEY}" \
  -e API_BASE_URL="${KUTANA_API_URL}" \
  -e GATEWAY_WS_URL="${KUTANA_GATEWAY_WS_URL}" \
  ghcr.io/dyerinnovation/kutana-mcp-server:latest

echo "Kutana MCP server started on port ${KUTANA_MCP_PORT}"
echo "MCP endpoint: http://localhost:${KUTANA_MCP_PORT}/mcp"
```

---

## Implementation Plan

### Phase 1: Core SKILL.md (immediate)
- Write the full `SKILL.md` with all capability sections
- Cover all 15 MCP tools with usage examples
- Include troubleshooting section

### Phase 2: Helper Scripts
- `connect.sh` — Docker-based MCP server launcher
- `mcp-bridge.py` — Generic Python bridge for frameworks without native MCP support

### Phase 3: Examples
- `meeting-assistant.md` — system prompt for a full meeting assistant agent
- `note-taker.md` — lightweight note-taking + task extraction agent

### Phase 4: ClawHub Publication
- Create ClawHub account for Dyer Innovation org
- Publish skill with proper metadata
- Set up automated version bumps on MCP server releases

### Phase 5: Claude Agent SDK Integration
- Update `docs/integrations/CLAUDE_AGENT_SDK.md` to reference the skill
- Add skill loading example to the example agent templates
- Consider bundling the skill in the `examples/meeting-assistant-agent/` directory

---

## Design Decisions

### Why wrap MCP in a skill rather than use MCP directly?

Three reasons:

1. **Context efficiency** — agents in long meetings need to preserve context for the meeting itself, not tool definitions. A skill summary costs ~50 tokens vs ~2,000 for all tool schemas.

2. **Agent guidance** — MCP tool descriptions are terse (optimized for schema readability). The skill body can include extended guidance: "When should I raise my hand?", "What message type should I use for a decision?", "How long should I wait before sending a follow-up?"

3. **Framework portability** — not all agent frameworks support MCP natively. A SKILL.md with a Python bridge script works everywhere.

### Why bundle all 4 capability areas in one skill?

Because in practice, agents that join a meeting need all four. A meeting assistant that can join but not chat, or chat but not check the queue, provides a degraded experience. Users bundle these capabilities together in their mental model of "participating in a meeting".

The frontmatter `capabilities` field allows future selective loading if needed, without requiring separate skill files.

### Skill vs. direct API calls?

The MCP server provides type-safe, authenticated, properly-scoped access to the Kutana APIs. Skills wrap MCP, not the raw REST API. This ensures:
- Auth is handled consistently
- Rate limiting is enforced server-side
- API contracts are versioned
- Agent actions are logged and auditable

---

## Related Files

- `integrations/openclaw-plugin/` — OpenClaw plugin source code
- `services/mcp-server/` — MCP server implementation
- `docs/integrations/OPENCLAW.md` — OpenClaw integration guide
- `docs/integrations/CLAUDE_AGENT_SDK.md` — Claude Agent SDK setup
- `docs/research/openclaw-skills-research.md` — Research findings that informed this design
