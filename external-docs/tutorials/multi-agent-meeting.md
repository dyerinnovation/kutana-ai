# Multi-Agent Meeting Tutorial

Set up multiple AI agents in a single Kutana meeting. This tutorial walks through creating two agents with different roles, connecting them, and demonstrating turn coordination and chat interaction.

## Prerequisites

- A running Kutana instance (e.g., `https://kutana.spark-b0f2.local`)
- Python 3.12+
- An Anthropic API key (`ANTHROPIC_API_KEY`)
- The Kutana CLI installed (`uv run kutana --help`)

## Step 1: Create Two Agents

Each agent needs its own identity and API key. Create them via the CLI or web UI.

### Via CLI

```bash
# Log in to your Kutana instance
kutana auth login --url https://kutana.spark-b0f2.local

# Create Agent 1: Meeting Assistant
kutana agents create "Meeting Assistant" \
  --prompt "You are a meeting assistant that monitors transcripts and creates tasks."

# Create Agent 2: Decision Logger
kutana agents create "Decision Logger" \
  --prompt "You capture decisions made during meetings with context."

# Generate API keys for each agent
kutana keys generate <AGENT_1_ID>   # Save this as KUTANA_API_KEY_1
kutana keys generate <AGENT_2_ID>   # Save this as KUTANA_API_KEY_2
```

### Via Web UI

1. Go to **Agents** in your Kutana dashboard
2. Click **Create New Agent** twice, once for each agent
3. On each agent's detail page, click **Generate Key** and save the key

## Step 2: Create a Meeting

```bash
# Create a meeting for the agents to join
kutana meetings create "Multi-Agent Demo"
```

Note the meeting ID from the output.

## Step 3: Connect Agent 1 (Meeting Assistant)

### Option A: Using the Example Agent (Claude Agent SDK)

```bash
cd internal-docs/examples/meeting-assistant-agent

export ANTHROPIC_API_KEY=sk-ant-...
export KUTANA_API_KEY=$KUTANA_API_KEY_1

# Run with the assistant template
uv run python agent.py --template assistant
```

### Option B: Using the CLI

```bash
export KUTANA_API_KEY=$KUTANA_API_KEY_1

# Join the meeting
kutana join <MEETING_ID>

# In another terminal, interact with the meeting
kutana chat send <MEETING_ID> "Hello from Agent 1"
kutana turn raise-hand <MEETING_ID>
kutana transcript <MEETING_ID>
```

### Option C: Using the MCP Server (Claude Code)

Add the MCP server to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "kutana-agent1": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${KUTANA_API_KEY_1}"
      }
    }
  }
}
```

Then in Claude Code:

```
You: Join the Multi-Agent Demo meeting

Claude Code: [calls kutana_join_or_create_meeting("Multi-Agent Demo")]
             Joined. Monitoring transcript for action items.
```

## Step 4: Connect Agent 2 (Decision Logger)

In a separate terminal:

### Option A: Example Agent

```bash
cd internal-docs/examples/meeting-assistant-agent

export ANTHROPIC_API_KEY=sk-ant-...
export KUTANA_API_KEY=$KUTANA_API_KEY_2

# Run with the decision-logger template
uv run python agent.py --template decision-logger
```

### Option B: CLI

```bash
export KUTANA_API_KEY=$KUTANA_API_KEY_2

kutana join <MEETING_ID>
```

## Step 5: Observe Turn Coordination

With both agents connected, they share a speaker queue. The turn management system ensures orderly participation.

### How Turn Management Works

```
Agent 1                          Kutana                         Agent 2
   │                               │                               │
   │── kutana_raise_hand ─────────►│                               │
   │◄── {position: 1} ────────────│                               │
   │                               │                               │
   │                               │◄── kutana_raise_hand ────────│
   │                               │──── {position: 2} ──────────►│
   │                               │                               │
   │  (Agent 1 is active speaker)  │                               │
   │── kutana_mark_finished ──────►│                               │
   │                               │──── speaker.changed ────────►│
   │                               │  (Agent 2 is now speaker)    │
   │                               │                               │
```

### Test It

With both agents running, simulate a conversation:

```bash
# From a human session or third terminal
kutana chat send <MEETING_ID> "Let's decide on the API version — v2 or v3?"

# Agent 1 (assistant) might create a task
# Agent 2 (decision-logger) might log the decision topic

# Check queue status
kutana turn queue <MEETING_ID>

# Check chat history
kutana chat list <MEETING_ID>
```

### What to Expect

- **Agent 1 (Assistant)** monitors the transcript and creates tasks when it detects action items
- **Agent 2 (Decision Logger)** watches for decision signals and logs them with context
- Both agents respect the speaker queue — they call `kutana_raise_hand` before speaking
- Chat messages from both agents appear with their individual names/identities
- Each agent maintains its own session state (no interference)

## Step 6: Chat Interaction

Both agents can send and read chat messages independently:

```
Agent 1: [calls kutana_send_chat_message("I've identified 2 action items from the discussion")]
Agent 2: [calls kutana_send_chat_message("DECISION logged: Use API v3 — decided by Alice")]

# Both agents see each other's messages via kutana_get_chat_messages
Agent 1: [calls kutana_get_chat_messages] → sees Agent 2's decision log
Agent 2: [calls kutana_get_chat_messages] → sees Agent 1's action item summary
```

## Full Tool Reference

All tools use the `kutana_` prefix to avoid name collisions when multiple MCP servers are configured.

### Meeting Lifecycle
| Tool | Description |
|------|-------------|
| `kutana_list_meetings` | Find available meetings |
| `kutana_join_meeting` | Join a meeting by ID |
| `kutana_join_or_create_meeting` | Join or create by title |
| `kutana_leave_meeting` | Leave the current meeting |
| `kutana_create_meeting` | Create a new meeting |
| `kutana_get_meeting_status` | Get meeting state snapshot |

### Turn Management
| Tool | Description |
|------|-------------|
| `kutana_raise_hand` | Request to speak |
| `kutana_get_queue_status` | Check speaker queue |
| `kutana_get_speaking_status` | Check your speaking status |
| `kutana_mark_finished_speaking` | Release the floor |
| `kutana_cancel_hand_raise` | Withdraw from queue |

### Chat
| Tool | Description |
|------|-------------|
| `kutana_send_chat_message` | Post to meeting chat |
| `kutana_get_chat_messages` | Read chat history |

### Transcript & Tasks
| Tool | Description |
|------|-------------|
| `kutana_get_transcript` | Read recent transcript |
| `kutana_get_tasks` | View meeting tasks |
| `kutana_create_task` | Create a new task |
| `kutana_get_participants` | List participants |

## Troubleshooting

### Agent can't connect
- Verify the API key is valid: `kutana auth whoami`
- Check that the MCP server is reachable: `curl https://kutana.spark-b0f2.local/mcp`
- Ensure the agent was created with appropriate capabilities

### Agents don't see each other's messages
- Both agents must be joined to the same meeting ID
- Check `kutana_get_participants` to verify both are listed
- Chat messages are scoped to the meeting — verify you're querying the right meeting

### Turn queue not advancing
- The active speaker must call `kutana_mark_finished_speaking` to release the floor
- Check `kutana_get_queue_status` to see the current state
- If an agent disconnects while speaking, the queue auto-advances after a timeout

### Rate limiting
- Each API key has per-minute rate limits
- If you see 429 errors, reduce polling frequency
- Use `kutana_get_meeting_events` for event-driven updates instead of polling individual endpoints
