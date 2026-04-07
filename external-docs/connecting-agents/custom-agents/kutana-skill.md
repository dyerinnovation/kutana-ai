# Kutana Meeting — Claude Code Skill

Connect Claude Code to live Kutana AI meetings. Read transcripts, manage turns, chat, and create tasks — all from within a coding session.

## Prerequisites

- A Kutana account with an agent API key (`cvn_...`)
- Get your key from the [Kutana dashboard](https://kutana.spark-b0f2.local) → Settings → API Keys

## Installation

### Option A — Copy skill to Claude Code (recommended)

```bash
mkdir -p ~/.claude/skills/kutana-meeting
cp skills/kutana-meeting/SKILL.md ~/.claude/skills/kutana-meeting/
```

The skill activates automatically when you mention meetings, standups, calls, or ask about transcripts.

### Option B — Add MCP server to Claude Code settings

In your `~/.claude/settings.json` (or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "kutana": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

Replace `YOUR_API_KEY` with your Kutana API key. Or use an environment variable:

```json
{
  "mcpServers": {
    "kutana": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${KUTANA_API_KEY}"
      }
    }
  }
}
```

Then set `KUTANA_API_KEY=cvn_...` in your environment.

### Option C — Use the connect script

For quick one-off joins without configuring MCP in settings:

```bash
export KUTANA_API_KEY=cvn_...
export KUTANA_URL=https://kutana.spark-b0f2.local

./scripts/connect.sh "Daily Standup"        # join by title
./scripts/connect.sh --id <meeting-uuid>    # join by ID
```

## Usage Examples

Once connected, speak naturally in Claude Code:

```
"Join the standup meeting"
→ Calls kutana_join_or_create_meeting("Daily Standup")

"What's being discussed right now?"
→ Calls kutana_get_transcript(last_n=20)

"Who's in the meeting?"
→ Calls kutana_get_participants()

"Raise my hand to ask about the API change"
→ Calls kutana_raise_hand(meeting_id, topic="API change question")

"Send a chat: 'I'll look into the auth bug'"
→ Calls kutana_send_chat_message(meeting_id, "I'll look into the auth bug")

"Create an action item: Review PR #42 before Friday"
→ Calls kutana_create_task(meeting_id, "Review PR #42 before Friday", priority="high")

"Leave the meeting"
→ Calls kutana_leave_meeting()
```

## Turn Management Workflow

```
kutana_raise_hand(meeting_id, topic="...")
  → if queue_position == 0: you have the floor immediately
  → if queue_position > 0: poll kutana_get_meeting_events(event_type="turn_your_turn")

kutana_start_speaking(meeting_id)          → confirm you have the floor
[say your piece via kutana_send_chat_message or voice]
kutana_mark_finished_speaking(meeting_id)  → release the floor

kutana_cancel_hand_raise(meeting_id)       → withdraw from queue
```

## Capability Configuration

Pass `capabilities` to `join_meeting()` to control what the agent can do:

| Capability | Description |
|---|---|
| `listen` | Receive transcript in real time (default) |
| `transcribe` | Buffer transcript segments (default) |
| `text_only` | No audio — text channels only |
| `voice` | Full audio input/output (requires TTS/STT setup) |
| `tts_enabled` | Text-to-speech output for agent responses |

Example:
```
kutana_join_meeting(meeting_id, capabilities=["listen", "transcribe", "text_only"])
```

