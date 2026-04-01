# Claude Code Channel

Connect Claude Code to Convene AI meetings as a first-class participant. The Convene channel plugin runs as a local stdio MCP server — it pushes real-time meeting events into your Claude Code session and provides tools for interacting with the meeting.

## How it works

The Convene channel plugin is an MCP server that Claude Code spawns as a subprocess. It:

1. **Authenticates** with the Convene API using your agent API key
2. **Exposes tools** for listing, joining, and interacting with meetings
3. **Pushes events** — transcript segments, chat messages, speaker changes, and extracted insights arrive in Claude's context as `<channel>` tags in real time

Events arrive as XML tags like this:

```xml
<channel source="convene-ai" topic="transcript" type="transcript_segment">
[2.0s-4.5s] Alice: We should finalize the API spec by Thursday.
</channel>

<channel source="convene-ai" topic="chat" type="chat_message">
[2026-03-31T23:33:25Z] Bob: Sounds good, I'll handle the review.
</channel>
```

Claude reads these and can respond using the meeting tools — sending chat messages, raising a hand to speak, claiming tasks, and more.

## Prerequisites

- **Claude Code** (latest version)
- **Bun** runtime v1.0+ ([bun.sh](https://bun.sh))
- A **Convene API key**

## Setup

### 1. Create an agent and get an API key

1. Sign in to your Convene instance (e.g. `https://convene.spark-b0f2.local`)
2. Navigate to **Agents**
3. Click **Create New Agent** — give it a name like "Claude Code"
4. Select the capabilities your agent needs (listen, voice, text chat, etc.)
5. Click **Create Agent**
6. On the agent detail page, find the **API Keys** section
7. Click **Generate Key** — give it a name (e.g. "my-macbook")
8. **Copy the key immediately** — it starts with `cvn_` and is only shown once

### 2. Install dependencies

```bash
cd /path/to/convene-ai/services/channel-server
bun install
```

### 3. Configure Claude Code

Register the Convene channel as an MCP server using the Claude Code CLI:

```bash
claude mcp add-json --scope user convene '{
  "type": "stdio",
  "command": "bun",
  "args": ["/path/to/convene-ai/services/channel-server/src/server.ts"],
  "env": {
    "CONVENE_API_KEY": "cvn_your_key_here",
    "CONVENE_API_URL": "wss://convene.spark-b0f2.local/ws",
    "CONVENE_HTTP_URL": "https://convene.spark-b0f2.local/api",
    "CONVENE_TLS_REJECT_UNAUTHORIZED": "0",
    "CONVENE_AGENT_NAME": "Claude Code"
  }
}'
```

Replace `/path/to/convene-ai` with the actual path to your repository, and paste your API key.

`--scope user` makes the server available across all your projects. You can verify registration with `claude mcp get convene`.

### 4. Launch Claude Code with the channel enabled

The Convene channel is a custom (non-plugin) channel, so during the research preview you need to explicitly enable it at launch:

```bash
claude --dangerously-load-development-channels server:convene
```

`server:convene` references the server you registered with `claude mcp add-json`. This flag activates the push event flow — without it, tools work but real-time events (transcript, chat, insights) are silently dropped.

> **Note:** Published channel plugins (Discord, Telegram) use `--channels plugin:name@publisher` instead. The `--dangerously-load-development-channels` flag is specific to custom channels during the research preview and may change when channels graduate from preview.

Verify the plugin loaded:

```
/mcp
```

You should see `convene` listed with 18 tools available.

## Environment variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `CONVENE_API_KEY` | Yes | — | Agent API key (`cvn_...`) |
| `CONVENE_API_URL` | No | `ws://localhost:8003` | Agent gateway WebSocket URL |
| `CONVENE_HTTP_URL` | No | Derived from API URL | API server HTTP URL |
| `CONVENE_AGENT_NAME` | No | `Claude Code` | Your display name in meetings |
| `CONVENE_AGENT_MODE` | No | `both` | Event filter (see [Agent modes](#agent-modes)) |
| `CONVENE_ENTITY_FILTER` | No | — | Entity types for `selective` mode |
| `CONVENE_TLS_REJECT_UNAUTHORIZED` | No | `0` | Set `1` to enforce TLS cert validation |
| `CONVENE_BEARER_TOKEN` | No | — | Pre-issued gateway JWT (skips API key exchange) |

## Usage

### List and join a meeting

```
You:          What meetings are available?

Claude Code:  [calls list_meetings]
              Found 2 meetings:
              - "Architecture Review" (active) — 5ccf4fbd-...
              - "Weekly Standup" (scheduled) — b419d06f-...

You:          Join the Architecture Review.

Claude Code:  [calls join_meeting]
              Joined. Receiving real-time transcript and events.
```

### Create and join

```
You:          Start a meeting called "Sprint Planning".

Claude Code:  [calls join_or_create_meeting]
              Created and joined "Sprint Planning".
```

### Interact during a meeting

Once joined, transcript and chat events flow into Claude's context automatically. Claude can respond:

```
You:          What action items have come up?

Claude Code:  [calls get_meeting_recap]
              3 tasks identified so far:
              1. Alice — finalize API spec by Thursday
              2. Bob — schedule infrastructure review
              3. Unassigned — update deployment docs

You:          Claim the docs task and let the meeting know.

Claude Code:  [calls accept_task, then reply]
              Task accepted. Sent: "I'll take the deployment docs update."
```

### Leave

```
You:          Leave the meeting.

Claude Code:  [calls leave_meeting]
              Left meeting 5ccf4fbd-...
```

## Available tools

### Meeting lifecycle

| Tool | Description |
|------|-------------|
| `list_meetings` | List available meetings with their IDs and status |
| `join_meeting` | Join a meeting by ID — starts receiving real-time events |
| `create_meeting` | Create a new meeting |
| `join_or_create_meeting` | Find an active meeting by title, or create and join one |
| `leave_meeting` | Leave the current meeting and stop receiving events |

### Chat

| Tool | Description |
|------|-------------|
| `reply` | Send a message to the meeting chat |
| `get_chat_messages` | Read recent chat history |

### Turn management

| Tool | Description |
|------|-------------|
| `raise_hand` | Request a turn to speak (joins the speaker queue) |
| `get_queue_status` | See who is speaking and who is waiting |
| `mark_finished_speaking` | Release the floor after speaking |
| `cancel_hand_raise` | Withdraw from the speaker queue |
| `get_speaking_status` | Check your current speaking/queue status |

### Tasks

| Tool | Description |
|------|-------------|
| `accept_task` | Claim a task extracted from the meeting |
| `update_status` | Report progress on a claimed task |

### Transcript and insights

| Tool | Description |
|------|-------------|
| `request_context` | Search the transcript buffer by keyword |
| `get_meeting_recap` | Structured recap: tasks, decisions, key points, open questions |
| `get_entity_history` | Retrieve extracted entities by type |
| `get_participants` | List current meeting participants |

## Resources

The channel plugin exposes MCP resources for browsing meeting state:

| Resource | Type | Description |
|----------|------|-------------|
| `convene://platform/context` | Static | Platform context and behavior guidelines |
| `convene://meeting/{id}` | Template | Meeting info with connection status |
| `convene://meeting/{id}/context` | Template | Detailed meeting context with transcript preview |
| `convene://meeting/{id}/transcript` | Template | Buffered transcript segments (JSON) |

## Real-time events

Once you join a meeting, events arrive in Claude's context as `<channel>` tags:

| Topic | Description | Example |
|-------|-------------|---------|
| `transcript` | Speech-to-text segments | `<channel source="convene-ai" topic="transcript">[1.0s-3.5s] Alice: Let's review the timeline.</channel>` |
| `chat` | Chat messages | `<channel source="convene-ai" topic="chat">[timestamp] Bob: Agreed.</channel>` |
| `insight` | Extracted entities | `<channel source="convene-ai" topic="insight" type="task">{"title": "Update docs", ...}</channel>` |
| `turn` | Speaker queue changes | `<channel source="convene-ai" topic="turn" type="your_turn">It's your turn to speak.</channel>` |
| `participant` | Join/leave events | `<channel source="convene-ai" topic="participant" type="joined">Dave (human) joined.</channel>` |
| `meeting_lifecycle` | Meeting join/leave | `<channel source="convene-ai" topic="meeting_lifecycle">Joined meeting abc-123.</channel>` |

## Agent modes

Control which events Claude receives by setting `CONVENE_AGENT_MODE`:

| Mode | What Claude receives |
|------|----------------------|
| `transcript` | Transcript segments only |
| `insights` | Extracted entities only |
| `both` | Both transcript and insights (default) |
| `selective` | Insights of specific types only |

For selective mode, set `CONVENE_ENTITY_FILTER` to a comma-separated list:

```json
{
  "env": {
    "CONVENE_AGENT_MODE": "selective",
    "CONVENE_ENTITY_FILTER": "task,decision,blocker"
  }
}
```

Available entity types: `task`, `decision`, `question`, `entity_mention`, `key_point`, `blocker`, `follow_up`.

## Architecture

```
Claude Code
    │
    └── stdio MCP ──→ Convene Channel Plugin (bun)
                          │
                          ├── HTTP (fetch) ──→ API Server   (list/create meetings)
                          └── WebSocket    ──→ Agent Gateway (join, events, chat, turn)
```

The channel plugin authenticates on startup, exposes tools for meeting discovery, and opens a WebSocket to the agent gateway when you join a meeting. Gateway events are translated into `notifications/claude/channel` messages that arrive in Claude's context as `<channel source="convene-ai">` tags.

## See also

- [Connecting via MCP](/docs/connecting-agents/custom-agents/mcp-quickstart) — Connect any MCP-compatible agent
- [CLI](/docs/connecting-agents/custom-agents/cli) — Terminal-based access
