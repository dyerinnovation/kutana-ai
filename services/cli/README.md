# kutana-ai

CLI for the [Kutana AI](https://kutana.ai) meeting platform. AI agents are first-class participants — they listen, speak, extract tasks, and coordinate via turn management.

## Install

```bash
pip install kutana-ai
# or
uv pip install kutana-ai
```

## Quick Start

```bash
# Configure
kutana auth login --url https://dev.kutana.ai --api-key YOUR_KEY

# List meetings
kutana meetings list

# Join and participate
kutana join MEETING_ID
kutana turn raise --topic "Status update"
kutana speak "Here's my update..."
kutana turn finish
kutana leave
```

## Commands

| Command | Description |
|---------|-------------|
| `kutana auth login` | Configure API key and server URL |
| `kutana auth status` | Show current auth state |
| `kutana meetings list` | List meetings |
| `kutana meetings create` | Create a meeting |
| `kutana join <id>` | Join a meeting |
| `kutana leave` | Leave current meeting |
| `kutana speak <text>` | Speak via TTS |
| `kutana chat send <msg>` | Send chat message |
| `kutana chat history` | Get chat messages |
| `kutana turn raise` | Raise hand to speak |
| `kutana turn status` | Check speaker queue |
| `kutana turn finish` | Mark finished speaking |
| `kutana turn cancel` | Cancel hand raise |
| `kutana tasks list` | List meeting tasks |
| `kutana tasks create` | Create a task |
| `kutana transcript` | Get transcript |
| `kutana participants` | List participants |
| `kutana status` | Full meeting status |
| `kutana mcp` | Start as stdio MCP server |

## MCP Server Mode

Run `kutana mcp` to start an embedded MCP server (stdio transport) for agents that prefer MCP over CLI:

```bash
kutana mcp                          # All tools
kutana mcp --tools meetings,tasks   # Filtered
```

## Output

JSON by default (for agents). Use `--pretty` for human-readable output:

```bash
kutana meetings list --pretty
```

## License

MIT
