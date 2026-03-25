# Agent Context Seeding Architecture

## Problem
Voice and coding agent APIs assume 1:1 dialogue between model and user. Convene AI meetings are N-way conversations. Agents need structured context to understand the meeting environment, participants, and (for late joiners) what's already happened.

## Solution: Three-Layer Context
Agent context is provided through three documents, layered from static to dynamic:

### Layer 1: Platform Context (`convene-ai-platform.md`)
- **Scope:** Fixed, versioned with the platform
- **Contents:** What Convene AI is, message formats (<channel> tags, insight stream entities), available tools (reply, accept_task, update_status, request_context), multi-speaker transcript format, agent behavior norms
- **When provided:** At agent connection time, never changes during a meeting
- **Maps to:** Claude Code Channel `instructions` field; Gemini Live `system_instruction`

### Layer 2: Meeting Context (`meeting-context.md`)
- **Scope:** Dynamic per meeting, generated at meeting creation or agent join
- **Contents:** Meeting title, purpose, attendees (names + roles), agenda items, linked background docs, expected outcomes, agent-specific instructions (e.g., "focus on backend action items")
- **Source:** Calendar invite, attendee list, meeting configuration
- **When provided:** At agent join time, may update if agenda changes mid-meeting
- **Maps to:** Initial channel notification or appended to system_instruction

### Layer 3: Meeting Recap (`meeting-recap.md`)
- **Scope:** Live, continuously updated during the meeting
- **Contents:** Key points discussed so far, decisions made, tasks assigned, open questions, current topic, active speakers summary
- **Source:** Snapshot of the Meeting Insight Stream (derivative of extraction pipeline output)
- **When provided:** Only for agents (or humans) joining after the meeting starts
- **Update frequency:** Every extraction batch (default: 30 seconds)
- **Maps to:** Burst of channel notifications or prepended context

## Integration Points

### Claude Code Channels
- Platform context → `instructions` field in MCP Server constructor
- Meeting context → First channel notification after connection
- Meeting recap → Burst of channel notifications with type="recap"

### Gemini Live API
- Platform context + meeting context → Combined `system_instruction`
- Meeting recap → Injected as text turns before live audio begins

### Human Participants (Future)
- Meeting recap → Displayed in UI when a participant joins late
- Could power a "catch me up" button in the meeting interface

## Relationship to Meeting Insight Stream
The recap generator subscribes to the same insight topics (meeting.{id}.insights) as other consumers. It maintains a rolling summary that's regenerated or updated each batch. This makes it a read-only consumer of the extraction pipeline — no new infrastructure needed.
