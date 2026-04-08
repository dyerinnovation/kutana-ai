# Kutana CLI Command Reference

Complete reference for all `kutana` CLI commands. All commands output JSON
to stdout. Errors are written to stderr as `{"error": "message"}` and the
process exits with code 1.

## Configuration

Config is stored in `~/.kutana/config.json`. Session state (current
meeting, token) is in `~/.kutana/session.json`.

---

## auth

### auth login

Authenticate with a Kutana server and save credentials.

```
kutana auth login --url <server_url> --api-key <key>
```

| Flag        | Required | Default                  | Description              |
|-------------|----------|--------------------------|--------------------------|
| `--url`     | no       | `https://dev.kutana.ai`  | Server base URL          |
| `--api-key` | yes      | --                       | API key (`cvn_...`)      |

**Output:**

```json
{"status": "authenticated", "url": "https://dev.kutana.ai"}
```

---

## meetings

### meetings list

List available meetings.

```
kutana meetings list
```

No flags.

**Output:**

```json
[
  {
    "id": "uuid-1234",
    "title": "Sprint Planning",
    "status": "active",
    "created_at": "2026-04-07T10:00:00Z",
    "participant_count": 4
  }
]
```

### meetings create

Create a new meeting.

```
kutana meetings create --title <title>
```

| Flag      | Required | Description         |
|-----------|----------|---------------------|
| `--title` | yes      | Meeting title       |

**Output:**

```json
{
  "id": "uuid-5678",
  "title": "Sprint Planning",
  "status": "scheduled",
  "created_at": "2026-04-07T10:00:00Z"
}
```

---

## join

Join a meeting by ID. Opens a WebSocket connection and starts receiving
real-time events (transcript, chat, speaker changes). Saves session state
to `~/.kutana/session.json`.

```
kutana join <meeting_id> [--capabilities <level>]
```

| Argument       | Required | Default      | Description                     |
|----------------|----------|--------------|---------------------------------|
| `meeting_id`   | yes      | --           | UUID of the meeting             |
| `--capabilities` | no    | `text_only`  | Capability level (see below)    |

**Capability values:**

- `text_only` -- chat and data channel only, no audio
- `tts_enabled` -- adds text-to-speech output
- `voice` -- bidirectional raw PCM16 audio via the sidecar WebSocket

**Output:**

```json
{
  "status": "joined",
  "meeting_id": "uuid-1234",
  "capabilities": ["listen", "transcribe", "data_channel"],
  "session_token": "tok_..."
}
```

---

## join-or-create

Find an active meeting by title and join it. If no match exists, create
one and join it.

```
kutana join-or-create --title <title> [--capabilities <level>]
```

| Flag             | Required | Default     | Description              |
|------------------|----------|-------------|--------------------------|
| `--title`        | yes      | --          | Title to search/create   |
| `--capabilities` | no       | `text_only` | Capability level         |

**Output:** Same as `join`.

---

## leave

Leave the current meeting. Closes the WebSocket connection and clears
session state.

```
kutana leave
```

No flags.

**Output:**

```json
{"status": "left", "meeting_id": "uuid-1234"}
```

---

## status

Get full meeting status: participants, speaker queue, recent activity.

```
kutana status
```

No flags. Requires an active session.

**Output:**

```json
{
  "meeting_id": "uuid-1234",
  "title": "Sprint Planning",
  "status": "active",
  "participants": [
    {"id": "p1", "name": "Alice", "role": "host"},
    {"id": "p2", "name": "Claude", "role": "agent"}
  ],
  "queue": {
    "active_speaker": {"id": "p1", "name": "Alice"},
    "waiting": []
  },
  "recent_chat_count": 12
}
```

---

## participants

List current meeting participants.

```
kutana participants
```

No flags. Requires an active session.

**Output:**

```json
[
  {"id": "p1", "name": "Alice", "role": "host", "status": "active"},
  {"id": "p2", "name": "Claude", "role": "agent", "status": "active"}
]
```

---

## turn

Speaker queue management commands.

### turn raise

Request a turn to speak. Adds you to the speaker queue.

```
kutana turn raise [--topic <topic>] [--priority <priority>]
```

| Flag         | Required | Default  | Description                          |
|--------------|----------|----------|--------------------------------------|
| `--topic`    | no       | --       | Short description of what to discuss |
| `--priority` | no       | `normal` | `normal` (FIFO) or `urgent` (front)  |

**Output:**

```json
{
  "hand_raise_id": "hr-uuid",
  "position": 2,
  "priority": "normal",
  "topic": "API design question"
}
```

### turn status

Get the current speaker queue.

```
kutana turn status
```

**Output:**

```json
{
  "active_speaker": {"id": "p1", "name": "Alice", "topic": null},
  "queue": [
    {"id": "p2", "name": "Claude", "position": 1, "topic": "Summary"}
  ],
  "your_status": "queued",
  "your_position": 1
}
```

### turn finish

Signal that you have finished speaking. Releases the active turn.

```
kutana turn finish
```

**Output:**

```json
{"status": "finished"}
```

### turn cancel

Withdraw from the speaker queue without speaking.

```
kutana turn cancel [--hand-raise-id <id>]
```

| Flag              | Required | Default | Description                     |
|-------------------|----------|---------|---------------------------------|
| `--hand-raise-id` | no       | --      | Specific hand raise to cancel   |

**Output:**

```json
{"status": "cancelled", "hand_raise_id": "hr-uuid"}
```

---

## speak

Speak text aloud via TTS. This is a convenience command that handles the
full turn lifecycle: raises hand, waits for your turn, synthesizes speech,
and marks finished.

```
kutana speak "<text>"
```

| Argument | Required | Description             |
|----------|----------|-------------------------|
| `text`   | yes      | Text to speak aloud     |

Requires `tts_enabled` or higher capability.

**Output:**

```json
{"status": "spoken", "text": "Here is my analysis..."}
```

---

## chat

### chat send

Send a text message to the meeting chat.

```
kutana chat send "<message>"
```

| Argument  | Required | Description          |
|-----------|----------|----------------------|
| `message` | yes      | Chat message text    |

**Output:**

```json
{"status": "sent", "message_id": "msg-uuid"}
```

### chat history

Read recent chat messages.

```
kutana chat history [--last-n <count>]
```

| Flag       | Required | Default | Description                  |
|------------|----------|---------|------------------------------|
| `--last-n` | no       | 50      | Number of messages to return |

**Output:**

```json
[
  {
    "id": "msg-uuid",
    "sender": "Alice",
    "text": "Let's discuss the timeline",
    "timestamp": "2026-04-07T10:05:00Z"
  }
]
```

---

## transcript

Get recent transcript segments.

```
kutana transcript [--last-n <count>]
```

| Flag       | Required | Default | Description                     |
|------------|----------|---------|---------------------------------|
| `--last-n` | no       | 50      | Number of segments to return    |

**Output:**

```json
[
  {
    "speaker": "Alice",
    "text": "I think we should prioritize the auth refactor.",
    "timestamp": "2026-04-07T10:03:12Z",
    "confidence": 0.95
  }
]
```

---

## context

Search the transcript buffer for segments relevant to a topic.

```
kutana context --query "<search_terms>" [--limit <count>]
```

| Flag      | Required | Default | Description                       |
|-----------|----------|---------|-----------------------------------|
| `--query` | yes      | --      | Topic or keywords to search for   |
| `--limit` | no       | 10      | Max matching segments to return   |

**Output:**

```json
[
  {
    "speaker": "Bob",
    "text": "The database migration should happen before the deploy.",
    "timestamp": "2026-04-07T10:02:45Z",
    "relevance_score": 0.87
  }
]
```

---

## entities

Retrieve extracted entities of a specific type from the meeting.

```
kutana entities --type <entity_type> [--limit <count>]
```

| Flag      | Required | Default | Description                         |
|-----------|----------|---------|-------------------------------------|
| `--type`  | yes      | --      | Entity type (see values below)      |
| `--limit` | no       | 50      | Max entities to return              |

**Entity types:** `task`, `decision`, `question`, `entity_mention`,
`key_point`, `blocker`, `follow_up`.

**Output (example for type=task):**

```json
[
  {
    "id": "ent-uuid",
    "type": "task",
    "content": "Refactor auth module",
    "assignee": "Alex",
    "source_speaker": "Alice",
    "timestamp": "2026-04-07T10:10:00Z"
  }
]
```

---

## recap

Fetch the current meeting recap: tasks, decisions, key points, and open
questions.

```
kutana recap
```

No flags. Requires an active session.

**Output:**

```json
{
  "tasks": [
    {"content": "Refactor auth module", "assignee": "Alex"}
  ],
  "decisions": [
    {"content": "Use PostgreSQL for the new service"}
  ],
  "key_points": [
    {"content": "Migration deadline is April 15"}
  ],
  "open_questions": [
    {"content": "Who will handle the API docs?"}
  ]
}
```

---

## tasks

### tasks list

List tasks extracted from a meeting.

```
kutana tasks list <meeting_id>
```

| Argument     | Required | Description       |
|--------------|----------|-------------------|
| `meeting_id` | yes      | Meeting UUID      |

**Output:**

```json
[
  {
    "id": "task-uuid",
    "title": "Refactor auth module",
    "assignee": "Alex",
    "status": "pending",
    "created_at": "2026-04-07T10:10:00Z"
  }
]
```

### tasks accept

Claim/accept a task.

```
kutana tasks accept <task_id>
```

| Argument  | Required | Description  |
|-----------|----------|--------------|
| `task_id` | yes      | Task UUID    |

**Output:**

```json
{"status": "accepted", "task_id": "task-uuid"}
```

### tasks update

Push a progress update for an accepted task.

```
kutana tasks update <task_id> --status <status> --message "<message>"
```

| Argument    | Required | Description                                         |
|-------------|----------|-----------------------------------------------------|
| `task_id`   | yes      | Task UUID                                           |
| `--status`  | yes      | `in_progress`, `completed`, `blocked`, `needs_review` |
| `--message` | yes      | Human-readable status update                        |

**Output:**

```json
{
  "task_id": "task-uuid",
  "status": "in_progress",
  "message": "Started refactoring the auth module"
}
```

---

## mcp

Start an MCP server exposing Kutana tools via the Model Context Protocol.

```
kutana mcp
```

No flags. Runs as a long-lived stdio MCP server. Use this only when the
consuming agent requires MCP transport rather than CLI invocation.

---

## Error Codes

All errors are returned as JSON on stderr with exit code 1.

| Error Message                  | Cause                                    | Resolution                          |
|--------------------------------|------------------------------------------|-------------------------------------|
| `not authenticated`            | No API key configured                    | Run `kutana auth login`             |
| `not in a meeting`             | Command requires active session          | Run `kutana join <id>` first        |
| `meeting not found`            | Invalid meeting ID                       | Check ID with `kutana meetings list`|
| `already in a meeting`         | Tried to join while already joined       | Run `kutana leave` first            |
| `not in speaker queue`         | Tried to finish/cancel without raising   | Run `kutana turn raise` first       |
| `insufficient capabilities`   | Action requires higher capability level  | Rejoin with appropriate capability  |
| `task not found`               | Invalid task ID                          | Check with `kutana tasks list`      |
| `connection failed`            | WebSocket connection error               | Check network and server URL        |
| `server error`                 | Server returned 5xx                      | Retry after a moment                |
