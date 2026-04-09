# Define Your Agent

> Source: https://platform.claude.com/docs/en/managed-agents/agent-setup

Create a reusable, versioned agent configuration.

---

An agent is a reusable, versioned configuration that defines persona and capabilities. It bundles the model, system prompt, tools, MCP servers, and skills that shape how Claude behaves during a session.

Create the agent once as a reusable resource and reference it by ID each time you start a session. Agents are versioned and easier to manage across many sessions.

> All Managed Agents API requests require the `managed-agents-2026-04-01` beta header. The SDK sets the beta header automatically.

## Agent configuration fields

| Field | Description |
| --- | --- |
| `name` | Required. A human-readable name for the agent. |
| `model` | Required. The Claude model that powers the agent. All Claude 4.5 and later models are supported. |
| `system` | A system prompt that defines the agent's behavior and persona. |
| `tools` | The tools available to the agent. Combines pre-built agent tools, MCP tools, and custom tools. |
| `mcp_servers` | MCP servers that provide standardized third-party capabilities. |
| `skills` | Skills that supply domain-specific context with progressive disclosure. |
| `callable_agents` | Other agents this agent can invoke for multi-agent orchestration (research preview). |
| `description` | A description of what the agent does. |
| `metadata` | Arbitrary key-value pairs for your own tracking. |

## Create an agent

```python
from anthropic import Anthropic

client = Anthropic()

agent = client.beta.agents.create(
    name="Coding Assistant",
    model="claude-sonnet-4-6",
    system="You are a helpful coding agent.",
    tools=[
        {"type": "agent_toolset_20260401"},
    ],
)
```

### curl

```bash
curl -fsSL https://api.anthropic.com/v1/agents \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d '{
    "name": "Coding Assistant",
    "model": "claude-sonnet-4-6",
    "system": "You are a helpful coding agent.",
    "tools": [{"type": "agent_toolset_20260401"}]
  }'
```

### CLI

```bash
ant beta:agents create \
  --name "Coding Assistant" \
  --model '{id: claude-sonnet-4-6}' \
  --system "You are a helpful coding agent." \
  --tool '{type: agent_toolset_20260401}'
```

> To use Claude Opus 4.6 with fast mode, pass `model` as an object: `{"id": "claude-opus-4-6", "speed": "fast"}`.

### Response

```json
{
  "id": "agent_01HqR2k7vXbZ9mNpL3wYcT8f",
  "type": "agent",
  "name": "Coding Assistant",
  "model": {
    "id": "claude-sonnet-4-6",
    "speed": "standard"
  },
  "system": "You are a helpful coding agent.",
  "description": null,
  "tools": [
    {
      "type": "agent_toolset_20260401",
      "default_config": {
        "permission_policy": { "type": "always_allow" }
      }
    }
  ],
  "skills": [],
  "mcp_servers": [],
  "metadata": {},
  "version": 1,
  "created_at": "2026-04-03T18:24:10.412Z",
  "updated_at": "2026-04-03T18:24:10.412Z",
  "archived_at": null
}
```

## Update an agent

Updating an agent generates a new version. Pass the current `version` to ensure you're updating from a known state.

```python
updated_agent = client.beta.agents.update(
    agent.id,
    version=agent.version,
    system="You are a helpful coding agent. Always write tests.",
)

print(f"New version: {updated_agent.version}")
```

### Update semantics

- **Omitted fields are preserved.** You only need to include the fields you want to change.
- **Scalar fields** (`model`, `system`, `name`, etc.) are replaced with the new value. `system` and `description` can be cleared by passing `null`. `model` and `name` are mandatory and cannot be cleared.
- **Array fields** (`tools`, `mcp_servers`, `skills`, `callable_agents`) are fully replaced by the new array. To clear an array field entirely, pass `null` or an empty array.
- **Metadata** is merged at the key level. Keys you provide are added or updated. Keys you omit are preserved. To delete a specific key, set its value to an empty string.
- **No-op detection.** If the update produces no change relative to the current version, no new version is created and the existing version is returned.

## Agent lifecycle

| Operation | Behavior |
| --- | --- |
| **Update** | Generates a new agent version. |
| **List versions** | Fetch the full version history to track changes over time. |
| **Archive** | The agent becomes read-only. New sessions cannot reference it, but existing sessions continue to run. |

### List versions

```python
for version in client.beta.agents.versions.list(agent.id):
    print(f"Version {version.version}: {version.updated_at.isoformat()}")
```

### Archive an agent

```python
archived = client.beta.agents.archive(agent.id)
print(f"Archived at: {archived.archived_at.isoformat()}")
```

### CLI

```bash
ant beta:agents:versions list --agent-id "$AGENT_ID"
ant beta:agents archive --agent-id "$AGENT_ID"
```
