---
name: convene
description: Join and participate in Convene AI meetings
requires:
  config:
    - plugins.entries.convene.config.apiKey
---

# Convene AI Meeting Skill

Use these tools to interact with Convene AI meetings.

## When to Use

- User asks to join, check, or monitor a meeting
- User asks about meeting transcripts, notes, or discussions
- User wants to create tasks or action items from a meeting
- User wants to create or schedule a new meeting

## Tools

### convene_list_meetings
List all available meetings. Use this first to find relevant meetings.

### convene_join_meeting
Join a specific meeting by ID. The agent will start receiving transcript updates.
- Requires: `meeting_id` (from list_meetings)

### convene_get_transcript
Get recent transcript segments from the current meeting.
- Optional: `last_n` (default: 50) — number of segments to return

### convene_create_task
Create a task or action item from a meeting discussion.
- Requires: `meeting_id`, `description`
- Optional: `priority` (low, medium, high, critical)

### convene_get_participants
List who is currently in the meeting.

### convene_create_meeting
Create a new meeting.
- Requires: `title`

## Example Workflow

1. `convene_list_meetings` → find the active meeting
2. `convene_join_meeting` with the meeting ID
3. `convene_get_transcript` periodically to monitor discussion
4. `convene_create_task` when you identify action items
5. Summarize key points when the user asks

## Guidelines

- Always list meetings first before trying to join one
- Check transcript regularly (every 30-60 seconds in active monitoring)
- Use appropriate priority levels for tasks
- Be concise in task descriptions — use action verbs
