# Start a Session

> Source: https://platform.claude.com/docs/en/managed-agents/sessions

Create a session to run your agent and begin executing tasks.

---

A session is a running agent instance within an environment. Each session references an agent and an environment (both created separately), and maintains conversation history across multiple interactions.

> All Managed Agents API requests require the `managed-agents-2026-04-01` beta header. The SDK sets the beta header automatically.

## Creating a session

A session requires an `agent` ID and an `environment` ID. Agents are versioned resources; passing in the `agent` ID as a string starts the session with the latest agent version.

```python
session = client.beta.sessions.create(
    agent=agent.id,
    environment_id=environment.id,
)
```

### Pin to a specific agent version

```python
pinned_session = client.beta.sessions.create(
    agent={"type": "agent", "id": agent.id, "version": 1},
    environment_id=environment.id,
)
```

### curl

```bash
curl -fsSL https://api.anthropic.com/v1/sessions \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d @- <<EOF
{
  "agent": "$AGENT_ID",
  "environment_id": "$ENVIRONMENT_ID"
}
EOF
```

### CLI

```bash
ant beta:sessions create \
  --agent "$AGENT_ID" \
  --environment "$ENVIRONMENT_ID"
```

## MCP authentication through vaults

If your agent uses MCP tools that require authentication, pass `vault_ids` at session creation:

```python
vault_session = client.beta.sessions.create(
    agent=agent.id,
    environment_id=environment.id,
    vault_ids=[vault.id],
)
```

## Starting the session

Creating a session provisions the environment and agent but does not start any work. To delegate a task, send events to the session using a user event:

```python
client.beta.sessions.events.send(
    session.id,
    events=[
        {
            "type": "user.message",
            "content": [
                {"type": "text", "text": "List the files in the working directory."}
            ],
        },
    ],
)
```

## Session statuses

| Status | Description |
|--------|-------------|
| `idle` | Agent is waiting for input, including user messages or tool confirmations. Sessions start in `idle`. |
| `running` | Agent is actively executing |
| `rescheduling` | Transient error occurred, retrying automatically |
| `terminated` | Session has ended due to an unrecoverable error |

## Other session operations

### Retrieve a session

```python
retrieved = client.beta.sessions.retrieve(session.id)
print(f"Status: {retrieved.status}")
```

### List sessions

```python
for session in client.beta.sessions.list():
    print(f"{session.id}: {session.status}")
```

### Archive a session

Archive a session to prevent new events from being sent while preserving its history:

```python
client.beta.sessions.archive(session.id)
```

### Delete a session

Delete a session to permanently remove its record, events, and associated container. A `running` session cannot be deleted; send an interrupt event if you need to delete it immediately.

Files, memory stores, environments, and agents are independent resources and are not affected by session deletion.

```python
client.beta.sessions.delete(session.id)
```

### CLI

```bash
ant beta:sessions list
ant beta:sessions retrieve --session-id "$SESSION_ID"
ant beta:sessions archive --session-id "$SESSION_ID"
ant beta:sessions delete --session-id "$SESSION_ID"
```
