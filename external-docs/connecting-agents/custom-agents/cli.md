# Convene CLI Reference

## Overview

The `convene` CLI tool wraps the Convene REST API for terminal-based access to meetings, agents, and tasks.

## Installation

```bash
cd services/cli
uv sync
```

Or add to your path:
```bash
uv tool install -e services/cli
```

## Authentication

```bash
# Login with email/password
convene login

# Credentials stored in ~/.convene/config.json
```

## Commands

### Meetings

```bash
# List meetings
convene meetings list

# Create a meeting
convene meetings create "Sprint Planning"

# Start a meeting
convene meetings start <meeting-id>

# End a meeting
convene meetings end <meeting-id>
```

### Agents

```bash
# List your agents
convene agents list

# Create an agent
convene agents create "My Assistant" --capabilities listen,transcribe
```

### API Keys

```bash
# Generate an API key for an agent
convene keys generate <agent-id> --name "my-key"
```

### Configuration

```bash
# Show current config
convene config show

# Set API URL
convene config set api_url http://localhost:8000
```

## Configuration File

Stored at `~/.convene/config.json`:

```json
{
  "api_url": "http://localhost:8000",
  "token": "<jwt-token>",
  "email": "user@example.com"
}
```

## See Also

- [Agent Platform Architecture](../technical/AGENT_PLATFORM.md)
- [MCP Auth Flow](../technical/MCP_AUTH.md)
