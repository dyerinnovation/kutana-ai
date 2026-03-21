# OpenClaw Integration Guide

## Overview

The Convene AI OpenClaw plugin (`@convene/openclaw-plugin`) gives OpenClaw agents native access to Convene meeting tools. Install the plugin and agents can join meetings, read transcripts, and create tasks from any OpenClaw channel (Slack, WhatsApp, etc.).

## Installation

```bash
openclaw plugins install @convene/openclaw-plugin
```

## Configuration

In your OpenClaw `config.yaml`:

```yaml
plugins:
  entries:
    convene:
      config:
        apiKey: "cvn_..."          # Convene API key
        mcpUrl: "http://localhost:3001/mcp"  # MCP server URL
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

## Skill

The plugin includes a SKILL.md that teaches agents when and how to use the tools:

```
skills/convene/SKILL.md
```

The skill is automatically available to OpenClaw agents when the plugin is installed.

## Architecture

```
OpenClaw Agent (Slack/WhatsApp/etc.)
    │
    │  Native tool calls
    ▼
@convene/openclaw-plugin
    │
    │  HTTP + Bearer token
    ▼
Convene MCP Server (http://localhost:3001/mcp)
    │
    │  API calls + WebSocket
    ▼
Convene API Server + Agent Gateway
```

## Example Usage

In Slack:
```
User: @agent join the standup meeting and tell me what's being discussed
Agent: [calls convene_list_meetings, convene_join_meeting, convene_get_transcript]
Agent: Here's what's being discussed in the standup...
```

## Development

The plugin source is at `integrations/openclaw-plugin/`:

```
integrations/openclaw-plugin/
├── openclaw.plugin.json    # Plugin manifest
├── package.json            # Node.js project
├── src/
│   ├── index.ts           # Plugin entry, registers tools
│   └── convene-client.ts  # HTTP client for MCP/API
└── skills/
    └── convene/
        └── SKILL.md       # Agent instructions
```

Build and test:
```bash
cd integrations/openclaw-plugin
npm install
npm run build
npm test
```
