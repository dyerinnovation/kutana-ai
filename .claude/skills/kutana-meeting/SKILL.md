---
name: kutana-meeting
description: >
  Access Kutana AI meeting context — transcripts, tasks, participants, and
  live meeting participation. TRIGGER on: meeting, kutana, standup, call,
  hand raise, speaker, transcript, action items, join meeting.
---

# Kutana Meeting Skill

## Setup

MCP server is configured at `https://kutana.spark-b0f2.local/mcp` (K3s cluster).
Add to `.claude/settings.json` with `Authorization: Bearer ${KUTANA_API_KEY}`.

## Joining a Meeting

```
1. kutana_list_meetings()               → find meeting by title/status
2. kutana_join_or_create_meeting(title)  → join active or create new
   OR kutana_join_meeting(meeting_id, capabilities=["listen","transcribe"])
3. kutana_get_meeting_status(meeting_id) → orient yourself (queue, participants, chat)
```

## Turn Management (raise → wait → start_speaking → finish)

```
1. kutana_raise_hand(meeting_id, topic="...")    → enter queue; queue_position=0 means floor is yours
2. kutana_get_meeting_events(event_type="turn_your_turn")  → poll until your turn
3. kutana_start_speaking(meeting_id)            → confirm you have the floor
4. [kutana_speak / send messages]
5. kutana_mark_finished_speaking(meeting_id)    → release floor, advance queue
```

Use `kutana_cancel_hand_raise(meeting_id)` to withdraw from queue.
Use `kutana_get_queue_status(meeting_id)` to see who's waiting.

## Chatting

```
kutana_send_chat_message(meeting_id, content, message_type)
  message_type: text | question | action_item | decision

kutana_get_chat_messages(meeting_id, limit=50, message_type=None)
```

## Reading Transcript

```
kutana_get_transcript(last_n=50)        → recent segments (must be joined)
kutana_get_participants()               → who is in the meeting
```

## Leaving

```
kutana_leave_meeting()
```

## Context Without Joining

```
kutana_list_meetings()                  → browse all meetings
kutana_get_tasks(meeting_id)            → action items
kutana_create_task(meeting_id, description, priority)
```

## Capability Options

| Capability | Effect |
|---|---|
| `listen` | Receive transcript (default) |
| `transcribe` | Buffer transcript segments (default) |
| `text_only` | No audio processing |
| `voice` | Audio input/output |
| `tts_enabled` | Text-to-speech output |
