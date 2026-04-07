# Meeting State Machine

State transitions for meetings, agent sessions, and the speaker queue.

## Meeting States

```
scheduled --> active --> ended
    |                     ^
    +-----> cancelled ----+
```

| State       | Description                                      |
|-------------|--------------------------------------------------|
| `scheduled` | Meeting created but not yet started               |
| `active`    | At least one participant has joined; live session  |
| `ended`     | Meeting concluded; transcript and recap finalized  |
| `cancelled` | Meeting was cancelled before becoming active       |

**Transitions:**

| From        | To          | Trigger                                |
|-------------|-------------|----------------------------------------|
| `scheduled` | `active`    | First participant joins                |
| `scheduled` | `cancelled` | Host cancels before anyone joins       |
| `active`    | `ended`     | Host ends meeting or all leave         |
| `cancelled` | --          | Terminal state                         |
| `ended`     | --          | Terminal state                         |

An agent can join a `scheduled` or `active` meeting. Joining a `scheduled`
meeting transitions it to `active`. Agents cannot join `ended` or
`cancelled` meetings.

## Agent Session States

```
disconnected --> joining --> joined --> left
                   |          |  ^       ^
                   |          |  |       |
                   |          v  |       |
                   |       speaking -----+
                   |          |
                   +----------+--> error
```

| State          | Description                                       |
|----------------|---------------------------------------------------|
| `disconnected` | Not connected to any meeting                      |
| `joining`      | WebSocket connecting; handshake in progress        |
| `joined`       | Connected and idle; receiving events               |
| `speaking`     | Holding the active speaker turn                    |
| `left`         | Gracefully disconnected from the meeting           |
| `error`        | Connection lost or fatal error                     |

**Transitions:**

| From           | To             | Trigger                             | CLI Command              |
|----------------|----------------|-------------------------------------|--------------------------|
| `disconnected` | `joining`      | Agent requests join                 | `kutana join <id>`       |
| `joining`      | `joined`       | WebSocket handshake completes       | (automatic)              |
| `joining`      | `error`        | Handshake fails                     | (automatic)              |
| `joined`       | `speaking`     | Agent becomes active speaker        | `kutana speak "..."`     |
| `joined`       | `left`         | Agent leaves meeting                | `kutana leave`           |
| `speaking`     | `joined`       | Agent finishes speaking             | `kutana turn finish`     |
| `speaking`     | `left`         | Agent leaves while speaking         | `kutana leave`           |
| `error`        | `disconnected` | Session cleared                     | (automatic)              |

## Speaker Queue States

The speaker queue is a FIFO priority queue. Each hand raise has its own
lifecycle.

```
not_raised --> queued --> active --> finished
                 |                    ^
                 +--> cancelled ------+
```

| State        | Description                                        |
|--------------|----------------------------------------------------|
| `not_raised` | Agent has not requested a turn                     |
| `queued`     | In the queue waiting for turn                      |
| `active`     | Currently the active speaker                       |
| `finished`   | Turn completed; removed from queue                 |
| `cancelled`  | Withdrew from queue before speaking                |

**Transitions:**

| From         | To          | Trigger                              | CLI Command              |
|--------------|-------------|--------------------------------------|--------------------------|
| `not_raised` | `queued`    | Agent raises hand                    | `kutana turn raise`      |
| `queued`     | `active`    | Previous speaker finishes; your turn | (automatic)              |
| `queued`     | `cancelled` | Agent cancels hand raise             | `kutana turn cancel`     |
| `active`     | `finished`  | Agent signals done speaking          | `kutana turn finish`     |

**Priority rules:**

- `normal` -- appended to end of queue (FIFO)
- `urgent` -- inserted at front of queue

When the active speaker finishes or leaves, the next person in the queue
is promoted to `active`.

## Convenience: kutana speak

The `kutana speak` command abstracts the full turn lifecycle into a single
call:

```
not_raised --> queued --> active --> [TTS playback] --> finished
```

Internally it executes: raise hand, wait for turn, send TTS text, mark
finished. If you need to hold the turn across multiple utterances, use
the individual `turn raise` / `turn finish` commands instead.

## Event Flow

While joined, the agent receives real-time events over the WebSocket:

| Event Type         | Data                                          |
|--------------------|-----------------------------------------------|
| `transcript`       | New transcript segment (speaker, text, ts)    |
| `chat`             | New chat message (sender, text, ts)           |
| `speaker_change`   | Active speaker changed                        |
| `queue_update`     | Speaker queue changed                         |
| `participant_join` | Someone joined the meeting                    |
| `participant_leave`| Someone left the meeting                      |
| `entity_extracted` | New entity found (task, decision, etc.)        |
| `meeting_ended`    | Meeting has ended                             |

The CLI handles these events internally and updates the local session
state. Use `kutana status`, `kutana transcript`, and `kutana chat history`
to query the accumulated state at any time.
