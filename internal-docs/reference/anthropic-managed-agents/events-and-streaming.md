# Session Event Stream

> Source: https://platform.claude.com/docs/en/managed-agents/events-and-streaming

Send events, stream responses, and interrupt or redirect your session mid-execution.

---

Communication with Claude Managed Agents is event-based. You send user events to the agent, and receive agent and session events back to track status.

> All Managed Agents API requests require the `managed-agents-2026-04-01` beta header. The SDK sets the beta header automatically.

## Event types

Events flow in two directions:
- **User events** are what you send to the agent to kick off a session and steer it as it progresses.
- **Session events**, **span events**, and **agent events** are sent to you for observability into your session state and agent progress.

Event type strings follow a `{domain}.{action}` naming convention.

### User events

| Type | Description |
| --- | --- |
| `user.message` | A user message with text content. |
| `user.interrupt` | Stop the agent mid-execution. |
| `user.custom_tool_result` | Response to a custom tool call from the agent. |
| `user.tool_confirmation` | Approve or deny an agent or MCP tool call when a permission policy requires confirmation. |
| `user.define_outcome` | Define an outcome for the agent to work toward. |

### Agent events

| Type | Description |
| --- | --- |
| `agent.message` | Agent response containing text content blocks. |
| `agent.thinking` | Agent thinking content, emitted separately from messages. |
| `agent.tool_use` | Agent invoked a pre-built agent tool (bash, file operations, etc.). |
| `agent.tool_result` | Result of a pre-built agent tool execution. |
| `agent.mcp_tool_use` | Agent invoked an MCP server tool. |
| `agent.mcp_tool_result` | Result of an MCP tool execution. |
| `agent.custom_tool_use` | Agent invoked one of your custom tools. Respond with a `user.custom_tool_result` event. |
| `agent.thread_context_compacted` | Conversation history was compacted to fit the context window. |
| `agent.thread_message_sent` | Agent sent a message to another multiagent thread. |
| `agent.thread_message_received` | Agent received a message from another multiagent thread. |

### Session events

| Type | Description |
| --- | --- |
| `session.status_running` | Agent is actively processing. |
| `session.status_idle` | Agent finished its current task and is waiting for input. Includes a `stop_reason`. |
| `session.status_rescheduled` | A transient error occurred and the session is retrying automatically. |
| `session.status_terminated` | Session ended due to an unrecoverable error. |
| `session.error` | An error occurred during processing. Includes a typed `error` object with a `retry_status`. |
| `session.outcome_evaluated` | An outcome evaluation has reached a terminal status. |
| `session.thread_created` | The coordinator spawned a new multiagent thread. |
| `session.thread_idle` | A multiagent thread finished its current work. |

### Span events

Span events are observability markers that wrap activity for timing and usage tracking.

| Type | Description |
| --- | --- |
| `span.model_request_start` | A model inference call has started. |
| `span.model_request_end` | A model inference call has completed. Includes `model_usage` with token counts. |
| `span.outcome_evaluation_start` | Outcome evaluation has started. |
| `span.outcome_evaluation_ongoing` | Heartbeat during an ongoing outcome evaluation. |
| `span.outcome_evaluation_end` | Outcome evaluation has completed. |

Every event includes a `processed_at` timestamp indicating when the event was recorded server-side.

## Sending events

Send a `user.message` event to start or continue the agent's work:

```python
client.beta.sessions.events.send(
    session.id,
    events=[
        {
            "type": "user.message",
            "content": [
                {
                    "type": "text",
                    "text": "Analyze the performance of the sort function in utils.py",
                },
            ],
        },
    ],
)
```

### Interrupt and redirect

```python
client.beta.sessions.events.send(
    session.id,
    events=[
        {"type": "user.interrupt"},
        {
            "type": "user.message",
            "content": [
                {
                    "type": "text",
                    "text": "Instead, focus on fixing the bug in line 42.",
                },
            ],
        },
    ],
)
```

## Streaming responses

Stream events from the session to receive real-time updates. Open the stream before sending events to avoid a race condition.

```python
with client.beta.sessions.events.stream(session.id) as stream:
    client.beta.sessions.events.send(
        session.id,
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": "Summarize the repo README"}],
            },
        ],
    )

    for event in stream:
        match event.type:
            case "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="")
            case "session.status_idle":
                break
            case "session.error":
                msg = event.error.message if event.error else "unknown"
                print(f"\n[Error: {msg}]")
                break
```

### Reconnecting to an existing session

Open a new stream and then list the full history to seed a set of seen event IDs. Tail the live stream while skipping any events already returned by the history list.

```python
with client.beta.sessions.events.stream(session.id) as stream:
    # Stream is open and buffering. List history before tailing live.
    seen_event_ids = {event.id for event in client.beta.sessions.events.list(session.id)}

    # Tail live events, skipping anything already seen
    for event in stream:
        if event.id in seen_event_ids:
            continue
        seen_event_ids.add(event.id)
        match event.type:
            case "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="")
            case "session.status_idle":
                break
```

## Listing event history

Fetch the full event history of a session:

```python
for event in client.beta.sessions.events.list(session.id):
    print(f"[{event.type}] {event.id}")
```

### curl

```bash
curl -sS "https://api.anthropic.com/v1/sessions/$SESSION_ID/events" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01"
```

### CLI

```bash
ant beta:sessions:events list --session-id "$SESSION_ID"
```
