# Scheduled Agent Participation — Research Notes

> Research for F2.9: autonomous AI agent joining recurring meetings on behalf of a user, with configurable autonomy levels.

---

## Overview

Scheduled agent participation lets users configure their AI agent to automatically join recurring meetings, participate on their behalf, and report back. The agent behaves as a first-class participant — the user doesn't need to be present.

This builds directly on the existing Convene MCP tools and the CoWork scheduled task system. A scheduled task calls `join_meeting` at the right time, runs the configured autonomy behavior, then posts a summary when the meeting ends.

---

## Use Cases

### Executive / Leadership
- Weekly standups the user attends but rarely speaks in — agent observes and surfaces blockers
- Board prep calls — agent extracts commitments and action items automatically
- All-hands meetings — agent summarizes key announcements and decisions

### Engineering
- Sprint planning — agent observer mode tracks task assignments without interrupting
- Architecture review — active mode, can ask clarifying questions via chat
- Incident retrospectives — delegate mode extracts action items and assigns them

### Sales / Customer Success
- Customer check-ins — reporter mode, summarizes status and flags risks
- Pipeline reviews — active mode, updates task statuses based on commitments heard

### Operations
- Vendor review calls — observer mode, no-talk participation
- Recurring team syncs — reporter mode, produces structured weekly digest

---

## Autonomy Levels

Four levels from passive observation to full delegation. Each builds on the previous.

### Level 0: Observer
The agent joins, listens to the full meeting, and produces a structured summary afterward. No interaction during the meeting.

**Behaviors:**
- Joins via `join_meeting` MCP tool
- Subscribes to transcript stream
- Does not raise hand, does not send chat
- On meeting end: produces summary (participants, decisions, action items)
- Posts summary to configured channel (chat, email, Slack)

**Use when:** The user wants a record and digest but doesn't need the agent to do anything during the meeting.

### Level 1: Reporter
Observer + live status posting. The agent posts periodic updates to meeting chat so participants know what it's tracking.

**Behaviors (all of Observer, plus):**
- Every N minutes (configurable), posts a brief chat summary: "Tracking: 3 action items so far. Current speaker: [name]."
- On task extraction: immediately posts task to chat with assignee and due date
- Participants can react with ✓ to confirm a task

**Use when:** The user's team should know the agent is active and what it's capturing.

### Level 2: Active
Reporter + can ask clarifying questions and request clarifications via chat or voice.

**Behaviors (all of Reporter, plus):**
- If a commitment is ambiguous (no owner, no due date), raises hand or posts chat asking for clarification
- Can respond to direct questions in chat ("@agent, who is assigned to the infra task?")
- Uses `raise_hand` → waits for turn → speaks a short clarifying question
- Can create tasks via `create_task` during the meeting

**Use when:** The meeting quality benefits from a participant that actively resolves ambiguity.

### Level 3: Delegate
Full proxy for the user. The agent can make commitments, accept action items, and represent the user's position.

**Behaviors (all of Active, plus):**
- Pre-meeting: reads briefing doc and user's open task list to understand current priorities
- Can respond to questions on the user's behalf ("Jonathan said he'll have the API spec ready by Friday")
- Can accept action items assigned to the user ("I'll accept that on Jonathan's behalf — he's heads down this week")
- Post-meeting: updates the user's task list with new commitments
- Flags conflicts: "Jonathan already has 3 high-priority tasks this week — this deadline may slip"

**Use when:** The user trusts the agent to represent them fully and cannot attend.

---

## Integration with Convene MCP Tools

The agent uses the existing MCP tool suite. No new protocol is needed — scheduled participation is a behavior layer on top of existing tools.

| Tool | Observer | Reporter | Active | Delegate |
|------|----------|----------|--------|----------|
| `join_meeting` | ✓ | ✓ | ✓ | ✓ |
| `get_transcript` | ✓ | ✓ | ✓ | ✓ |
| `get_chat_messages` | ✓ | ✓ | ✓ | ✓ |
| `send_chat_message` | — | ✓ | ✓ | ✓ |
| `get_queue_status` | — | — | ✓ | ✓ |
| `raise_hand` | — | — | ✓ | ✓ |
| `mark_finished_speaking` | — | — | ✓ | ✓ |
| `get_meeting_status` | ✓ | ✓ | ✓ | ✓ |
| `create_task` | — | — | ✓ | ✓ |
| `get_tasks` | ✓ | ✓ | ✓ | ✓ |
| `leave_meeting` | ✓ | ✓ | ✓ | ✓ |

### Pre-Meeting Context (Delegate mode)
Before joining, the delegate-level agent calls:
- `get_tasks` — user's open action items
- `get_meeting_context` — agenda, attendees, previous meeting recap
- Reads a user-provided briefing document (MCP resource or injected system prompt)

---

## Scheduled Task Integration

The scheduling layer uses the CoWork `create_scheduled_task` MCP tool (or `anthropic-skills:schedule` skill).

### Task Structure

```
Schedule: recurring, matches meeting cadence (e.g., every Monday 9:00 AM)
Prompt: |
  Join meeting [meeting_id] as [user]'s delegate.
  Autonomy level: observer
  Post summary to: [channel_id]
  On completion: email summary to [user_email]
```

### Meeting ID Resolution
Two approaches:
1. **Static**: user provides the Convene meeting ID directly (for recurring Convene-native meetings)
2. **Calendar-driven**: agent checks calendar integration for upcoming meetings matching a title/series pattern, resolves the meeting ID dynamically (requires Phase 10 calendar sync)

### Post-Meeting Reporting
After `leave_meeting`, the agent:
1. Calls `get_tasks` to retrieve all tasks created during the meeting
2. Calls `get_transcript` for the full transcript
3. Generates a structured summary using Claude Sonnet
4. Posts via configured channel: chat message, Slack, email

---

## Implementation Phases

### Phase A — Observer Mode (MVP)
**Scope**: Scheduled task joins meeting, listens, produces end-of-meeting summary.

1. Extend `join_meeting` to support a `mode: observer` flag (no audio capability required)
2. Implement `MeetingObserver` agent template (in `examples/`)
3. Create scheduled task definition for observer mode
4. Implement post-meeting summary prompt chain (transcript → structured summary via Claude)
5. Implement summary delivery: post to meeting chat + return in scheduled task result
6. Write docs and milestone test

### Phase B — Reporter Mode
**Scope**: Agent posts periodic status updates and confirms extracted tasks.

1. Implement periodic heartbeat loop in agent (N-minute intervals)
2. Add `send_chat_message` calls with live extraction status
3. Task confirmation flow: send proposed task → participants react → agent confirms via `create_task`

### Phase C — Active Mode
**Scope**: Agent asks clarifying questions, resolves ambiguities.

1. Implement ambiguity detector in extraction pipeline (missing owner/due date → trigger question)
2. Turn management integration: `raise_hand` → wait for turn → speak question
3. Chat-based Q&A handler: parse `@agent` mentions, respond

### Phase D — Delegate Mode
**Scope**: Full proxy, pre-meeting briefing, post-meeting task sync.

1. Pre-meeting context assembly (open tasks, briefing doc)
2. Commitment acceptance and conflict detection
3. Post-meeting task list update
4. User notification with conflict flags

---

## Key Design Decisions

### Agent Identity
The scheduled agent joins as the user's named agent (not as "Convene Bot"). Participants see it as "[User]'s Agent" in the participant list. This is intentional — transparency about AI presence.

### Consent & Transparency
All participants are notified on join that an AI agent is present. This is a platform-level guarantee, not delegated to the user configuring the schedule.

### Rate Limiting
Observer mode agents do not produce output during the meeting, so they consume no turn-management resources. Active and delegate mode agents are subject to the same rate limits as other agents.

### Failure Handling
If the agent loses its connection mid-meeting:
1. Attempt reconnect up to 3 times with exponential backoff
2. If reconnect fails, post to chat: "Agent disconnected — continuing to monitor transcript from checkpoint"
3. On reconnect, fetch transcript from checkpoint and continue

### Privacy
Scheduled participation must be opt-in at the meeting level. The meeting owner must allow agent observers when creating the meeting. By default, meetings only allow agents whose owners are participants.

---

## Open Questions

1. **Calendar integration timing**: Phase A uses static meeting IDs. Dynamic calendar-driven scheduling requires Phase 10 calendar sync — do we want to ship a limited calendar integration earlier?

2. **Summary format**: Should the post-meeting summary be a fixed format or configurable per-user? A template system (Jinja2 or Claude prompt template) would let teams customize.

3. **Multi-meeting handling**: Can a single scheduled agent attend multiple concurrent meetings? Initial answer: no — one agent connection per meeting. Multiple meetings require multiple scheduled tasks.

4. **Billing**: Observer-mode agent sessions should be metered as agent-minutes (same as active agents). Delegate mode is higher-value — consider a premium billing tier.

5. **Delegate trust level**: Should delegate mode require explicit meeting-owner approval (like a human guest), or is the owner's team membership sufficient authorization?
