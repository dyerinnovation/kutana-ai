---
name: kutana
description: Join and participate in Kutana AI meetings
requires:
  config:
    - plugins.entries.kutana.config.apiKey
---

# Kutana AI Meeting Skill

Use these tools to interact with Kutana AI meetings.

## When to Use

- User asks to join, check, or monitor a meeting
- User asks about meeting transcripts, notes, or discussions
- User wants to create tasks or action items from a meeting
- User wants to raise their hand or speak in a meeting
- User wants to create or schedule a new meeting

## Tools

### kutana_list_meetings
List all available meetings. Use this first to find relevant meetings.

### kutana_join_meeting
Join a specific meeting by ID. The agent will start receiving transcript updates.
- Requires: `meeting_id` (from list_meetings)
- Optional: `capabilities` — array of strings: `["listen","transcribe"]` (default), `["text_only"]`, `["voice"]`, `["tts_enabled"]`

### kutana_get_transcript
Get recent transcript segments from the current meeting.
- Optional: `last_n` (default: 50) — number of segments to return

### kutana_create_task
Create a task or action item from a meeting discussion.
- Requires: `meeting_id`, `description`
- Optional: `priority` (low, medium, high, critical)

### kutana_get_participants
List who is currently in the meeting.

### kutana_create_meeting
Create a new meeting.
- Requires: `title`

## Turn Management Tools

### kutana_raise_hand
Request a turn to speak. Enter the speaker queue.
- Requires: `meeting_id`
- Optional: `priority` (normal | urgent), `topic`
- Returns: `queue_position` (0 = immediate floor), `hand_raise_id`

### kutana_start_speaking
Confirm you have the floor and are actively speaking.
- Requires: `meeting_id`
- Call after `raise_hand` returns `queue_position=0` or after `turn_your_turn` event

### kutana_mark_finished_speaking
Signal you are done speaking. Advances the queue to the next speaker.
- Requires: `meeting_id`

### kutana_get_queue_status
See who is speaking and who is waiting.
- Requires: `meeting_id`

### kutana_cancel_hand_raise
Withdraw from the speaker queue.
- Requires: `meeting_id`
- Optional: `hand_raise_id`

## Chat Tools

### kutana_send_chat_message
Send a message to the meeting chat.
- Requires: `meeting_id`, `content`
- Optional: `message_type` (text | question | action_item | decision)

### kutana_get_chat_messages
Get chat history.
- Requires: `meeting_id`
- Optional: `limit` (default 50), `message_type`

## Turn Workflow

```
1. kutana_raise_hand(meeting_id, topic="...")
   → queue_position=0: floor is yours immediately
   → queue_position>0: wait for your turn

2. kutana_start_speaking(meeting_id)    → confirm you have the floor

3. [speak — send chat messages or voice]

4. kutana_mark_finished_speaking(meeting_id)  → release floor
```

## Guidelines

- Always list meetings first before trying to join one
- Check transcript regularly (every 30-60 seconds in active monitoring)
- Use appropriate priority levels for tasks
- Be concise in task descriptions — use action verbs
- Always call mark_finished_speaking when done — never leave the floor open
