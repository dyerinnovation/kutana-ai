# Claude Agent SDK Templates

## Purpose
Verify all 4 agent templates (assistant, summarizer, action-tracker, decision-logger) running against a live meeting, custom system prompts, and Claude Desktop/Claude Code MCP configuration.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- [03-mcp-auth-flow.md](./03-mcp-auth-flow.md) verified
- `$TOKEN`, `$AGENT_ID`, `$API_KEY` exported
- API server (8000), gateway (8003), MCP server (3001) running
- `ANTHROPIC_API_KEY` environment variable set (valid Claude API key)
- An active meeting with audio (or plan to speak into browser room simultaneously)

## Step 1: Set Up Environment

```bash
cd examples/meeting-assistant-agent

# Set required environment variables
export ANTHROPIC_API_KEY="sk-ant-..."  # Your Claude API key
export MCP_BEARER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY" | jq -r '.token')
export MCP_SERVER_URL="http://localhost:3001"

echo "MCP_BEARER_TOKEN set: ${MCP_BEARER_TOKEN:0:20}..."
```

## Step 2: Create and Start a Test Meeting

```bash
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Agent SDK Test",
    "platform": "kutana",
    "scheduled_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')

curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start \
  -H "Authorization: Bearer $TOKEN" > /dev/null

echo "MEETING_ID=$MEETING_ID"
```

## Step 3: Test Assistant Template (default)

```bash
uv run python agent.py --template assistant
```

The agent will:
1. Call `list_meetings` to find available meetings
2. Call `join_meeting` with the active meeting ID
3. Monitor transcript via `get_transcript` every 10-15 seconds
4. Extract action items and create tasks via `create_task`

Expected output: Agent logs showing tool calls and responses. Let it run for 30-60 seconds.

Press `Ctrl+C` to stop.

## Step 4: Test Summarizer Template

```bash
uv run python agent.py --template summarizer
```

The agent will:
1. Join the active meeting
2. Generate interim summaries every 5 minutes (key topics, decisions, open questions)
3. On exit, produce a final summary

Expected: Agent logs show periodic summary generation.

Press `Ctrl+C` to stop after observing at least one summary attempt.

## Step 5: Test Action-Tracker Template

```bash
uv run python agent.py --template action-tracker
```

The agent will:
1. Join the meeting
2. Focus on action item detection ("I'll do X", "By Friday", blocking items)
3. Create tasks in format: `[@name] Action description (due: date)`

Expected: If transcript contains action-oriented language, tasks are created.

Press `Ctrl+C` to stop.

## Step 6: Test Decision-Logger Template

```bash
uv run python agent.py --template decision-logger
```

The agent will:
1. Join the meeting
2. Capture decisions with format: `DECISION: [what] — Decided by: [who], Context: [why]`
3. Track rejected alternatives

Expected: Agent monitors for decision language in transcript.

Press `Ctrl+C` to stop.

## Step 7: Test Custom System Prompt

```bash
uv run python agent.py --system-prompt "You are a meeting note-taker. Focus only on listing participants and topics discussed. Use bullet points."
```

Expected: Agent uses the custom prompt instead of a template.

## Step 8: Test with Different Model

```bash
uv run python agent.py --template assistant --model claude-haiku-4-5-20251001
```

Expected: Agent runs with the specified model (faster, lower cost).

## Step 9: Verify Tasks Were Created

```bash
curl -s http://localhost:8000/api/v1/tasks?meeting_id=$MEETING_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | {description, priority}'
```

Expected: Tasks created by the agent templates appear in the list.

## Step 10: Claude Desktop / Claude Code MCP Configuration

To configure the agent as an MCP remote server for Claude Desktop or Claude Code:

### Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "kutana": {
      "url": "http://localhost:3001/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>"
      }
    }
  }
}
```

### Claude Code (`.claude/settings.json`):
```json
{
  "mcpServers": {
    "kutana": {
      "type": "url",
      "url": "http://localhost:3001/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_BEARER_TOKEN>"
      }
    }
  }
}
```

After configuring, verify tools appear in Claude Desktop/Code:
- `list_meetings`
- `join_meeting`
- `get_transcript`
- `create_task`
- `get_participants`
- `create_new_meeting`
- `start_meeting_session`
- `end_meeting_session`
- `join_or_create_meeting`
- `subscribe_channel`
- `publish_to_channel`

## Verification Checklist

- [ ] `ANTHROPIC_API_KEY` and `MCP_BEARER_TOKEN` set correctly
- [ ] Assistant template joins meeting and calls `get_transcript`
- [ ] Summarizer template attempts periodic summaries
- [ ] Action-tracker template monitors for action items
- [ ] Decision-logger template monitors for decisions
- [ ] Custom `--system-prompt` overrides template
- [ ] `--model` flag selects different Claude model
- [ ] Tasks created by agents appear in `/api/v1/tasks`
- [ ] MCP tools appear in Claude Desktop/Code after configuration

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ANTHROPIC_API_KEY not set` | Export a valid Claude API key |
| Agent can't find meetings | Ensure meeting is in "active" status |
| Agent joins but no transcripts | Need audio input — open browser room and speak, or stream audio via gateway |
| `MCP_BEARER_TOKEN` expired | Re-exchange: `curl -s -X POST .../token/mcp -H "X-API-Key: $API_KEY"` |
| Claude Desktop tools not showing | Restart Claude Desktop after config change. Verify JSON syntax |
| Rate limit on Claude API | Use `--model claude-haiku-4-5-20251001` for lower rate limits |

## Cleanup

```bash
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN" > /dev/null

cd ../..  # Return to project root
```
