---
name: convene-meeting
description: >
  Access Convene AI meeting context — transcripts, tasks, participants, and
  live meeting participation. TRIGGER on: meeting, convene, standup, call,
  hand raise, speaker, transcript, action items, join meeting.
---

# Convene Meeting Skill

## Setup

MCP server must be configured in Claude Code settings (see `README.md`).

## Joining a Meeting

```
1. list_meetings()              → find meeting by title/status
2. join_or_create_meeting(title) → join active or create new
   OR join_meeting(meeting_id, capabilities=["listen","transcribe"])
3. get_meeting_status(meeting_id) → orient yourself (queue, participants, chat)
```

## Turn Management (raise → wait → start_speaking → finish)

```
1. raise_hand(meeting_id, topic="...")    → enter queue; queue_position=0 means floor is yours
2. get_meeting_events(event_type="turn_your_turn")  → poll until it's your turn
3. start_speaking(meeting_id)            → confirm you have the floor
4. [speak / send messages]
5. mark_finished_speaking(meeting_id)    → release floor, advance queue
```

Use `cancel_hand_raise(meeting_id)` to withdraw from queue.
Use `get_queue_status(meeting_id)` to see who's waiting.

## Chatting

```
send_chat_message(meeting_id, content, message_type)
  message_type: text | question | action_item | decision

get_chat_messages(meeting_id, limit=50, message_type=None)
```

## Reading Transcript

```
get_transcript(last_n=50)        → recent segments (must be joined)
get_participants()               → who is in the meeting
```

## Leaving

```
leave_meeting()
```

## Context Without Joining

```
list_meetings()                  → browse all meetings
get_tasks(meeting_id)            → action items
create_task(meeting_id, description, priority)
```

## Capability Options

| Capability | Effect |
|---|---|
| `listen` | Receive transcript (default) |
| `transcribe` | Buffer transcript segments (default) |
| `text_only` | No audio processing |
| `voice` | Audio input/output |
| `tts_enabled` | Text-to-speech output |
