# Milestone M_APRIL — April Release E2E Test Playbook

> **Target:** April 6-10, 2026
> **Pass criteria:** All 4 multi-party scenarios complete without errors. Turn management, chat, and Claude Code channel all functional.

## Prerequisites

```bash
# Infrastructure running
docker compose ps  # postgres, redis, livekit all healthy

# Services running
uv run uvicorn services.api_server.main:app --reload --port 8000
PYTHONPATH=... .venv/bin/uvicorn agent_gateway.main:app --reload --port 8003
uv run python -m services.mcp_server.main  # port 3000

# Environment
AGENT_GATEWAY_JWT_SECRET=<set>
ANTHROPIC_API_KEY=<set>
REDIS_URL=redis://localhost:6379/0
```

---

## Scenario A: 1 Human + 1 Agent

**Goal:** Verify basic turn management and chat between one human and one AI agent.

### Setup
- Create a meeting via API: `POST /api/v1/meetings`
- Human opens meeting room in browser
- Agent connects via MCP (Claude Code or example agent)

### Test Steps

**Turn Management:**
1. Agent calls `raise_hand` → receives queue position (1)
2. Human browser shows agent in queue (speaker queue panel visible)
3. Agent calls `get_queue_status` → confirms it is active speaker
4. Agent calls `mark_finished_speaking` → queue clears
5. Human presses hand-raise button in browser → enters queue
6. Human is now active speaker; agent sees update via `get_queue_status`

**Chat:**
1. Agent calls `send_chat_message` with "Hello from the agent"
2. Human browser shows message in chat panel with agent attribution
3. Human types a message in browser chat → sends
4. Agent calls `get_chat_messages` → sees human's message in history

**Meeting Status:**
1. Agent calls `get_meeting_status` → response includes: participants list, speaker queue, active speaker, recent chat messages

### Pass Criteria
- [ ] Turn queue updates propagate to all participants in real time (<500ms)
- [ ] Chat messages delivered to all participants in real time
- [ ] `get_meeting_status` returns accurate state snapshot
- [ ] No errors in service logs

---

## Scenario B: 2 Humans + 1 Agent

**Goal:** Verify that multi-human + single agent works correctly, especially turn ordering.

### Setup
- Create meeting
- Human 1 opens meeting in Browser Tab 1
- Human 2 opens meeting in Browser Tab 2 (or separate browser/incognito)
- Agent connects via MCP

### Test Steps

**Turn Management:**
1. Human 1 raises hand → position 1
2. Agent calls `raise_hand` → position 2
3. Human 2 raises hand → position 3
4. All three participants see correct queue order
5. Human 1 finishes (releases turn) → agent advances to position 1
6. Agent calls `mark_finished_speaking` → Human 2 advances

**Chat:**
1. All three participants send a chat message
2. All three see all messages with correct attribution
3. Late joiner (Human 2 refreshes) → receives last 50 messages on reconnect

### Pass Criteria
- [ ] Queue position is correct for 3 concurrent participants
- [ ] Turn transitions preserve order (no jumps, no skips)
- [ ] Chat visible to all participants including new/rejoining ones
- [ ] No race conditions in Redis atomic operations

---

## Scenario C: 1 Human + Multiple Agents

**Goal:** Verify agent coordination and queue management with multiple agents.

### Setup
- Create meeting
- Human opens meeting in browser
- Agent 1 connects (e.g., `examples/meeting-assistant-agent/` — template 1)
- Agent 2 connects (different API key, different agent identity)
- Agent 3 connects (optional, if 3-agent support is stable)

### Test Steps

**Multi-Agent Turn Coordination:**
1. All agents call `raise_hand` in rapid succession
2. Queue shows agents in order of hand-raise timestamp
3. Agent 1 calls `mark_finished_speaking` → Agent 2 advances
4. Agent 2 calls `cancel_hand_raise` → Agent 3 advances
5. Human raises hand → enters queue at next position

**Independent Agent State:**
1. Agent 1 calls `get_queue_status` → sees its own position
2. Agent 2 calls `get_speaking_status` → shows it is active speaker
3. Each agent maintains independent session (no state bleed)

**Multi-Agent Chat:**
1. Each agent sends a distinct chat message
2. Human sees all messages with correct per-agent attribution (not merged)
3. `get_chat_messages` from any agent returns all messages in chronological order

### Pass Criteria
- [ ] 3+ agents can hold simultaneous sessions without session state collision
- [ ] Queue correctly orders all agents + human by raise timestamp
- [ ] Each agent's `get_queue_status` returns its own position (not a global view that leaks other agents' positions)
- [ ] Agent identity in chat is per-agent (name/id from API key), not generic

---

## Scenario D: Multiple Humans + Multiple Agents

**Goal:** Full multi-party meeting. This is the launch demo scenario.

### Setup
- Create meeting
- 2 humans in browser (separate tabs or machines)
- 2 agents via MCP (separate API keys)
- (Optional) 1 Claude Code session via channel

### Test Steps

**Full Queue Scenario:**
1. All participants raise hand / call `raise_hand` within 5 seconds of each other
2. Queue shows all 4+ participants in timestamp order
3. Each participant takes a turn (human finishes via browser button, agent via `mark_finished_speaking`)
4. Full rotation completes without any participant stuck in queue

**Full Chat Scenario:**
1. Each participant sends a chat message
2. All participants see all messages
3. Filter test: `get_chat_messages` with sender_type filter returns only agent messages

**Meeting Status Snapshot:**
1. At peak (all connected, 2 in queue): call `get_meeting_status`
2. Response includes: all 4+ participants, current speaker, queue with positions, last 10 chat messages
3. Verify participant list distinguishes human vs. agent type

**Claude Code Channel (if wired):**
1. Claude Code session connects via channel server
2. Appears in participant list with `source: "claude-code"` attribution
3. Can raise hand, send chat, read transcript via channel

### Pass Criteria
- [ ] All 4+ participants functional simultaneously with no service errors
- [ ] `get_meeting_status` reflects real-time state accurately
- [ ] No WebSocket connection drops under concurrent load
- [ ] All quality gates pass: `ruff check . && mypy --strict . && pytest -x -v`
- [ ] Service logs show no ERROR level entries during test

---

## Launch Checklist

Before marking M_APRIL complete:

- [ ] All 4 scenarios above pass
- [ ] `docs/integrations/CLAUDE_CODE_CHANNEL.md` written and accurate
- [ ] `examples/meeting-assistant-agent/` updated with turn + chat examples
- [ ] OpenClaw plugin updated with new MCP tool definitions
- [ ] TASKLIST.md M_APRIL milestone checked off
- [ ] PROGRESS.md entry written
- [ ] HANDOFF.md updated with launch state
