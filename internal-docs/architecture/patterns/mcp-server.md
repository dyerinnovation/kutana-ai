# MCP Server Architecture

## Overview
The MCP server (`services/mcp-server/`) exposes Convene AI tools to Claude and MCP-compatible clients via Streamable HTTP transport. It runs as a Docker container.

## Transport
- **Streamable HTTP** (not STDIO) — production-ready, Docker-compatible
- Endpoint: `http://localhost:3001/mcp`
- Config: `stateless_http=True, json_response=True` on FastMCP constructor
- Entry point: `mcp.run(transport="streamable-http")`

## Tools
| Tool | Description |
|------|-------------|
| `list_meetings()` | List available meetings |
| `join_meeting(meeting_id, capabilities)` | Exchange API key → gateway JWT → WebSocket connect → join meeting |
| `leave_meeting()` | Disconnect from meeting |
| `get_transcript(last_n)` | Get buffered transcript segments |
| `get_tasks(meeting_id)` | Get tasks for a meeting |
| `create_task(meeting_id, description, priority)` | Create a task |
| `get_participants()` | List meeting participants |

## Resources
- `meeting://{meeting_id}` — meeting details + connection status
- `meeting://{meeting_id}/transcript` — full transcript segments

## Internal Architecture
- `api_client.py` — HTTP client for API server (token exchange, CRUD via aiohttp)
- `gateway_client.py` — WebSocket client for agent gateway (connect, join, buffer transcripts)
- `settings.py` — `MCPServerSettings` (MCP_API_KEY, MCP_AGENT_CONFIG_ID, API_BASE_URL, GATEWAY_WS_URL, MCP_HOST, MCP_PORT)

## Docker
- `docker compose up mcp-server` — runs on port 3001
- Environment vars set on the container: `MCP_API_KEY`, `MCP_AGENT_CONFIG_ID`
- Uses `host.docker.internal` to reach host services (API server, gateway)

## Client Configuration
```json
{
  "mcpServers": {
    "convene": {
      "url": "http://localhost:3001/mcp"
    }
  }
}
```
