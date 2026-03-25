# @convene/openclaw-plugin

OpenClaw plugin that provides native Convene AI meeting tools for agents.

## Installation

```bash
openclaw plugins install @convene/openclaw-plugin
```

## Configuration

Add to your OpenClaw `config.yaml`:

```yaml
plugins:
  entries:
    convene:
      config:
        apiKey: "cvn_your_api_key_here"
        mcpUrl: "http://localhost:3001/mcp"  # Optional, defaults to localhost
```

## Available Tools

| Tool | Description |
|------|-------------|
| `convene_list_meetings` | List available meetings |
| `convene_join_meeting` | Join a meeting by ID |
| `convene_get_transcript` | Get recent transcript segments |
| `convene_create_task` | Create a task from meeting context |
| `convene_get_participants` | List meeting participants |
| `convene_create_meeting` | Create a new meeting |

## Development

```bash
npm install
npm run build
npm test
```

## How It Works

The plugin communicates with the Convene MCP server (Streamable HTTP) using OAuth 2.1 Bearer token authentication. On first tool call, it exchanges the configured API key for a short-lived JWT, then uses that token for all subsequent requests.

## See Also

- [Integration Guide](../../external-docs/openclaw/plugin-guide.md)
- [MCP Auth Flow](../../external-docs/agent-platform/connecting/mcp-auth.md)
