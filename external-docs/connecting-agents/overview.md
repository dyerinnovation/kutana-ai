# Connecting Agents to Convene

## Overview

There are two ways to bring AI agents into Convene meetings: **Custom Agents** that you build and connect yourself, and **Managed Agents** that Convene runs for you.

## Custom Agents

Custom agents are agents you build, deploy, and control. You connect them to Convene meetings via MCP (Model Context Protocol) and they participate as first-class meeting members — listening to transcripts, extracting tasks, posting to chat, and even speaking via TTS.

**You control:**
- The agent's code and logic
- System prompts and behavior
- Which meetings it joins
- What capabilities it uses

**Connection options:**
- [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart) — Connect any MCP-compatible agent via Streamable HTTP
- [Claude Agent SDK](/docs/connecting-agents/custom-agents/claude-agent-sdk) — Build agents with the Claude Agent SDK
- [Claude Code Channel](/docs/connecting-agents/custom-agents/claude-code-channel) — Use Claude Code as a meeting participant
- [OpenClaw Plugin](/docs/connecting-agents/custom-agents/openclaw-plugin) — Connect via OpenClaw channels
- [Convene Skill](/docs/connecting-agents/custom-agents/convene-skill) — Pre-built skill for OpenClaw agents
- [Convene CLI](/docs/connecting-agents/custom-agents/cli) — Terminal-based access

## Managed Agents

Managed agents are pre-built agents available in the Convene dashboard. Select one, assign it to a meeting, and Convene runs it — no code required.

**What you get:**
- One-click activation from the dashboard
- Pre-configured prompts optimized for each use case
- Automatic lifecycle management (joins, listens, produces output, leaves)
- Output visible in the meeting sidebar and post-meeting recap

**Tiers:**
- **Free tier**: Bring your own Anthropic API key
- **Premium tier**: API credits included with your Convene plan

See [Managed Agents](/docs/connecting-agents/managed-agents/overview) for the full list and activation guide.

## Comparison

| | Custom Agents | Managed Agents |
|---|---|---|
| Setup | You build + connect | One-click activation |
| Code required | Yes | No |
| Prompt control | Full | Pre-configured |
| Connection | MCP / Channel | Built-in |
| API key | Your own | Your own (free) or included (premium) |
| Examples | Your custom bot, Claude Code | Meeting Summarizer, Action Tracker |

## Authentication

All agents — custom and managed — authenticate via API key + OAuth 2.1 token exchange. See [MCP Authentication](/docs/connecting-agents/custom-agents/mcp-auth) for the full flow.
