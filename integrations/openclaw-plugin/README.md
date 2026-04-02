# @kutana/openclaw-plugin

OpenClaw plugin that provides native Kutana AI meeting tools for agents.

## Installation

```bash
openclaw plugins install @kutana/openclaw-plugin
```

## Configuration

Add to your OpenClaw `config.yaml`:

```yaml
plugins:
  entries:
    kutana:
      config:
        apiKey: "cvn_your_api_key_here"
        mcpUrl: "https://kutana.spark-b0f2.local/mcp"  # Optional, defaults to hosted server
```

Get your API key from the [Kutana dashboard](https://kutana.spark-b0f2.local) → your agent → API Keys → Generate Key.

## Available Tools

| Tool | Description |
|------|-------------|
| `kutana_list_meetings` | List available meetings |
| `kutana_join_meeting` | Join a meeting by ID |
| `kutana_get_transcript` | Get recent transcript segments |
| `kutana_create_task` | Create a task from meeting context |
| `kutana_get_participants` | List meeting participants |
| `kutana_create_meeting` | Create a new meeting |

## Development

```bash
npm install
npm run build
npm test
```

## How It Works

The plugin communicates with the Kutana MCP server (Streamable HTTP) using OAuth 2.1 Bearer token authentication. On first tool call, it exchanges the configured API key for a short-lived JWT, then uses that token for all subsequent requests.

## See Also

- [Integration Guide](../../external-docs/openclaw/plugin-guide.md)
- [MCP Auth Flow](../../external-docs/agent-platform/connecting/mcp-auth.md)
