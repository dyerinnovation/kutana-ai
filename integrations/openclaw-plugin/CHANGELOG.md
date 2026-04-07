# Changelog

## 1.0.0 (2026-04-07)

### Added
- 27 MCP tools covering full meeting lifecycle, turn management, chat, data channels, and events.
- ClawHub distribution config (`clawhub.json`) for publishing to the skill marketplace.
- `kutana_get_tasks` — retrieve tasks for a meeting.
- `kutana_get_summary` — structured meeting summary (title, decisions, key points, action items).
- `kutana_set_context` — inject pre-meeting context (agenda, notes, docs).
- `kutana_start_meeting` — transition a meeting from scheduled to active.
- `kutana_end_meeting` — transition a meeting from active to completed.
- `kutana_join_or_create_meeting` — find and join an active meeting by title, or create one.
- `kutana_subscribe_channel` — subscribe to a data channel for structured messages.
- `kutana_publish_to_channel` — publish structured data to a channel.
- `kutana_get_channel_messages` — read buffered data channel messages.
- `kutana_get_meeting_events` — poll real-time gateway events (turn changes, joins, chat).

## 0.1.0 (2026-03-07)

### Added
- Initial release with 16 meeting tools.
- Meeting lifecycle: list, join, create, leave.
- Transcript retrieval and task creation.
- Turn management: raise hand, cancel, start/finish speaking, queue status.
- Chat: send messages, get messages, meeting status overview.
- OpenClaw plugin manifest and TypeScript SDK client.
