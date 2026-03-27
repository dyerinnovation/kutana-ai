# Claude Code Standup Agent Demo

A step-by-step demo showing Claude Code joining a Convene AI standup meeting as a first-class participant — appearing in the participant grid, monitoring the transcript, and delivering a standup update when called on.

---

## Prerequisites

- Claude Code (latest)
- Access to a running Convene AI instance
- A Convene API key (Agent scope)

---

## 1. Get an API Key

1. Sign in to your Convene instance
2. Go to **Settings → API Keys**
3. Click **Generate Key** and select the **Agent** scope
4. Copy the key — it starts with `cvn_`

---

## 2. Configure Claude Code

### Set the environment variable

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export CONVENE_API_KEY="cvn_your_key_here"
```

Reload your shell:

```bash
source ~/.zshrc
```

### Add the MCP server

Edit `~/.claude/settings.json` and add the `convene` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "convene": {
      "type": "http",
      "url": "http://convene.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${CONVENE_API_KEY}"
      }
    }
  }
}
```

> **Note:** Replace `convene.spark-b0f2.local` with your Convene instance hostname if different.

### Verify the connection

Restart Claude Code, then run:

```
/mcp
```

You should see `convene` listed with 20+ available tools.

---

## 3. Demo Flow

The full standup demo runs through seven steps. You can run these as prompts in a Claude Code session, or Claude Code can execute them autonomously when given the right system prompt.

### Step 1 — List available meetings

```
convene_list_meetings()
```

**Example response:**
```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Daily Standup",
    "status": "active",
    "participant_count": 4
  },
  {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "title": "Q2 Planning",
    "status": "scheduled"
  }
]
```

Pick the active standup meeting and copy its `id`.

---

### Step 2 — Join the meeting

Join with `tts_enabled` so Claude Code can speak when it gets the floor. This is the step that makes Claude Code appear in the participant grid.

```
convene_join_meeting(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  capabilities=["text_only", "tts_enabled"]
)
```

**Example response:**
```json
{
  "status": "joined",
  "meeting_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "granted_capabilities": ["text_only", "tts_enabled"],
  "participant_name": "Claude Code"
}
```

At this point Claude Code appears as **"Claude Code"** (role: agent) in the participant grid in every browser that has the meeting open.

---

### Step 3 — Read the transcript

Poll the recent transcript to understand the meeting context before speaking.

```
convene_get_transcript(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  last_n=20
)
```

**Example response:**
```json
{
  "segments": [
    {
      "speaker_name": "Alice",
      "text": "Okay everyone, let's do standups. Bob, you want to start?",
      "start_time": "2026-03-26T09:01:12Z"
    },
    {
      "speaker_name": "Bob",
      "text": "Sure. Yesterday I finished the auth refactor. Today I'm on the deploy pipeline.",
      "start_time": "2026-03-26T09:01:24Z"
    },
    {
      "speaker_name": "Alice",
      "text": "Great. Let's hear from Claude next.",
      "start_time": "2026-03-26T09:02:05Z"
    }
  ]
}
```

---

### Step 4 — Poll for the cue

Watch the transcript for the trigger phrase (e.g., `"let's hear from Claude"`). Use `convene_get_meeting_events` to poll for new events without reading the full transcript every time.

```
convene_get_meeting_events(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  event_types=["transcript.segment"]
)
```

**Example response when cue arrives:**
```json
{
  "events": [
    {
      "event_type": "transcript.segment",
      "payload": {
        "speaker_name": "Alice",
        "text": "Let's hear from Claude next.",
        "timestamp": "2026-03-26T09:02:05Z"
      }
    }
  ]
}
```

When the transcript contains your trigger phrase, proceed to Step 5.

---

### Step 5 — Raise hand

Enter the speaker queue to signal readiness to speak.

```
convene_raise_hand(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  priority="normal",
  topic="standup update"
)
```

**Example response:**
```json
{
  "queue_position": 1,
  "hand_raise_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "estimated_wait": "immediately",
  "current_speaker": null
}
```

---

### Step 6 — Wait for the floor

Poll `convene_get_meeting_events` for a `speaker.changed` event that names Claude Code as the active speaker, or call `convene_get_queue_status` to check position.

```
convene_get_queue_status(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
)
```

**Example response when Claude Code is up:**
```json
{
  "current_speaker": {
    "participant_id": "d4e5f6a7-b8c9-0123-def0-234567890123",
    "name": "Claude Code"
  },
  "queue": [],
  "your_position": 0,
  "total_in_queue": 0
}
```

When `current_speaker.name` is `"Claude Code"`, proceed to speak.

---

### Step 7 — Deliver the standup update

Call `convene_start_speaking` with the standup text. The text is synthesized via TTS and mixed into the room audio.

```
convene_start_speaking(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  text="Yesterday I reviewed the transcript pipeline and identified three edge cases in the speaker diarization logic. Today I'll be monitoring the meeting for action items and flagging any commitments I detect. No blockers."
)
```

**Example response:**
```json
{
  "status": "speaking",
  "started_at": "2026-03-26T09:02:10Z"
}
```

---

### Step 8 — Release the floor

When finished, hand the floor back so the next speaker can go.

```
convene_mark_finished_speaking(
  meeting_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
)
```

**Example response:**
```json
{
  "status": "finished",
  "next_speaker": null,
  "queue_remaining": 0
}
```

---

## Full Autonomous Demo Prompt

Paste this into a Claude Code session after completing the setup above:

```
You are a standup agent participating in today's Daily Standup meeting.

1. Call convene_list_meetings and find the active "Daily Standup" meeting.
2. Join it with capabilities=["text_only", "tts_enabled"].
3. Read the transcript with convene_get_transcript (last 20 segments).
4. Poll convene_get_meeting_events every 10 seconds, watching for any segment
   where someone says "let's hear from Claude" or "Claude, your turn" or similar.
5. When you see that cue, raise your hand with topic="standup update".
6. Poll convene_get_queue_status until you are the current speaker.
7. Deliver your standup using convene_start_speaking with this text:
   "Yesterday I joined the meeting platform and verified the participant grid.
    Today I'll be monitoring transcripts and flagging action items.
    No blockers."
8. Call convene_mark_finished_speaking to release the floor.
9. Continue monitoring the transcript for action items until the meeting ends
   or someone says "that's a wrap".
```

---

## How Agents Appear in the Participant Grid

When an agent calls `convene_join_meeting`, the agent gateway broadcasts a `participant_update` event to all connected browser sessions. The meeting room UI adds the agent to the participant grid with:

- **Name:** the agent's configured display name (e.g., "Claude Code")
- **Role:** `agent` (shown as a label under the name)
- **Avatar:** initials fallback (no camera feed)

The agent tile updates in real time — a green pulse ring appears when the agent is actively speaking (TTS in progress).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `convene` not listed in `/mcp` | Settings not saved or Claude Code not restarted | Save `settings.json` and restart |
| `401 Unauthorized` on tool calls | API key not set or expired | Re-export `CONVENE_API_KEY` |
| Agent not visible in participant grid | Agent gateway not running | Check `kubectl logs -n convene deploy/agent-gateway` |
| `tts_not_enabled` error on start_speaking | Joined without `tts_enabled` capability | Leave and rejoin with `capabilities=["text_only", "tts_enabled"]` |
| Cue never detected | Transcript polling too slow | Decrease poll interval; check STT pipeline is running |

---

## See Also

- [Claude Code Channel docs](../../external-docs/agent-platform/connecting/claude-code-channel.md) — Full tool reference
- [MCP Auth](../../external-docs/agent-platform/connecting/mcp-auth.md) — OAuth 2.1 Bearer token flow
- [Agent Platform Overview](../../external-docs/agent-platform/overview.md) — Architecture and agent tiers
