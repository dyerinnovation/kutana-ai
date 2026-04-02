# Kutana CLI Reference

## Overview

The `kutana` CLI tool wraps the Kutana REST API for terminal-based access to meetings, agents, and tasks.

## Quick Install

```bash
curl -LsSf https://kutana.ai/install.sh | bash
```

This will install `git` and `uv` if needed, clone the Kutana repository, and install the CLI to your PATH.

## Install from Source

If you prefer to install manually:

```bash
git clone https://github.com/dyerinnovation/kutana-ai.git
cd kutana-ai
uv tool install -e services/cli
```

## Authentication

```bash
# Login with email/password
kutana login

# Credentials stored in ~/.kutana/config.json
```

## Commands

### Meetings

```bash
# List meetings
kutana meetings list

# Create a meeting
kutana meetings create "Sprint Planning"

# Start a meeting
kutana meetings start <meeting-id>

# End a meeting
kutana meetings end <meeting-id>
```

### Agents

```bash
# List your agents
kutana agents list

# Create an agent
kutana agents create "My Assistant" --capabilities listen,transcribe
```

### API Keys

```bash
# Generate an API key for an agent
kutana keys generate <agent-id> --name "my-key"
```

### Configuration

```bash
# Show current config
kutana config show

# Set API URL
kutana config set api_url http://localhost:8000
```

## Configuration File

Stored at `~/.kutana/config.json`:

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
