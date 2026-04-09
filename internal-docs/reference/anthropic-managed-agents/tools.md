# Tools

> Source: https://platform.claude.com/docs/en/managed-agents/tools

Configure tools available to your agent.

---

Claude Managed Agents provides a set of built-in tools that Claude can use autonomously within a session. You control which tools are available by specifying them in the agent configuration.

Custom, user-defined tools are also supported. Your application executes these tools separately and sends the tool results back to Claude.

> All Managed Agents API requests require the `managed-agents-2026-04-01` beta header. The SDK sets the beta header automatically.

## Available tools

The agent toolset includes the following tools. All are enabled by default when you include the toolset in your agent configuration.

| Tool | Name | Description |
|---|---|---|
| Bash | `bash` | Execute bash commands in a shell session |
| Read | `read` | Read a file from the local filesystem |
| Write | `write` | Write a file to the local filesystem |
| Edit | `edit` | Perform string replacement in a file |
| Glob | `glob` | Fast file pattern matching using glob patterns |
| Grep | `grep` | Text search using regex patterns |
| Web fetch | `web_fetch` | Fetch content from a URL |
| Web search | `web_search` | Search the web for information |

## Configuring the toolset

Enable the full toolset with `agent_toolset_20260401` when creating an agent. Use the `configs` array to disable specific tools or override their settings.

```python
agent = client.beta.agents.create(
    name="Coding Assistant",
    model="claude-sonnet-4-6",
    tools=[
        {
            "type": "agent_toolset_20260401",
            "configs": [
                {"name": "web_fetch", "enabled": False},
            ],
        },
    ],
)
```

### Disabling specific tools

```json
{
  "type": "agent_toolset_20260401",
  "configs": [
    { "name": "web_fetch", "enabled": false },
    { "name": "web_search", "enabled": false }
  ]
}
```

### Enabling only specific tools

Start with everything off and enable only what you need:

```json
{
  "type": "agent_toolset_20260401",
  "default_config": { "enabled": false },
  "configs": [
    { "name": "bash", "enabled": true },
    { "name": "read", "enabled": true },
    { "name": "write", "enabled": true }
  ]
}
```

## Custom tools

Custom tools allow you to extend Claude's capabilities. Each tool defines a contract: you specify what operations are available and what they return; Claude decides when and how to call them.

```python
agent = client.beta.agents.create(
    name="Weather Agent",
    model="claude-sonnet-4-6",
    tools=[
        {
            "type": "agent_toolset_20260401",
        },
        {
            "type": "custom",
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        },
    ],
)
```

Once defined at the agent level, the agent will invoke the tools through the course of a session. See events-and-streaming.md for the full custom tool call flow.

### Best practices for custom tool definitions

- **Provide extremely detailed descriptions.** This is the most important factor in tool performance. Aim for at least 3-4 sentences per tool description.
- **Consolidate related operations into fewer tools.** Rather than creating a separate tool for every action, group them into a single tool with an `action` parameter.
- **Use meaningful namespacing in tool names.** Prefix names with the resource (e.g., `db_query`, `storage_read`).
- **Design tool responses to return only high-signal information.** Return semantic, stable identifiers rather than opaque internal references.
