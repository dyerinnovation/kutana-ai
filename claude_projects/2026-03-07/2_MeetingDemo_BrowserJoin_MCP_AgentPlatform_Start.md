# Plan: Meeting Demo + Browser Join + MCP Auth + Agent Platform + Product Roadmap

**Date:** 2026-03-07
**Status:** In Progress

## Overview

Implement the full meeting join experience with browser audio, MCP OAuth 2.1 auth, multi-tier agent platform, and supporting infrastructure.

## Part A: Core Meeting Join (Phase 1)

### A1: MCP Server OAuth 2.1 Authorization
- Add `POST /api/v1/token/mcp` — exchanges API key for MCP JWT
- JWT validation middleware in MCP server
- Scope-based access control (meetings:read, meetings:join, tasks:write)
- Wire auth into FastMCP

### A2: Meeting Lifecycle Endpoints
- `PATCH /api/v1/meetings/{id}` — update meeting
- `POST /api/v1/meetings/{id}/start` — set active
- `POST /api/v1/meetings/{id}/end` — set completed

### A3: Browser Meeting Room (Mic + Transcripts)
- New page `MeetingRoomPage.tsx` at `/meetings/:id/room`
- getUserMedia → AudioWorklet → PCM16 at 16kHz
- WebSocket to gateway with meeting JWT
- Real-time transcript display
- `POST /api/v1/token/meeting` — meeting JWT for human participants

### A4: New MCP Tools
- `create_meeting(title, platform)`
- `start_meeting(meeting_id)`
- `end_meeting(meeting_id)`
- `join_or_create_meeting(title)`

### A5: AgentSessionORM Writes
- On join: create AgentSessionORM record
- On leave: update record with disconnect time

### A6: Frontend Meeting Updates
- Start/End/Join Room buttons
- Status badges (scheduled/active/completed)
- Navigation to meeting room

### A7: Demo Script
- Full E2E loop: register → agent → key → meeting → start → audio → transcripts

## Part B: Agent Platform (Phase 2)

### B1: Convene CLI Tool
- Python CLI with typer
- Commands: login, agents, meetings, keys
- WebSocket meeting join with mic audio

### B2: OpenClaw Plugin + Skill
- TypeScript plugin for OpenClaw
- Native Convene tools
- SKILL.md for agent instructions

### B3: Claude Agent SDK Integration Guide
- Update examples/meeting-assistant-agent/
- OAuth 2.1 Bearer token usage
- Additional agent templates

### B4: Prebuilt Agent Templates
- AgentTemplateORM + HostedAgentSessionORM models
- CRUD API endpoints
- Frontend template browser
- Agent runner worker

### B5: API Key Security
- expires_at column
- Rate limiting middleware (Redis)
- Audit log table
- Encrypted Anthropic API key storage

### B6: Claude Code Skill
- `.claude/skills/convene-meeting/SKILL.md`
- Uses MCP server for meeting context

### B7: Capability-Based Channel Routing
- Redis pub/sub routing by capability
- MCP tools: subscribe_channel, publish_to_channel

### B8: Log Monitoring CoWork Task
- Daily log monitor task doc
- Log checking script

## Team Structure

| Agent | Responsibilities |
|-------|-----------------|
| Lead | Coordinate, A7, B6, B8 |
| backend-auth | A1, A2, A4, A5, B5 |
| frontend-audio | A3, A6, B4 frontend |
| agent-channels | B1, B2, B3, B4 backend, B7 |

## Dependencies

```
A1 (MCP Auth) → A4 (MCP tools) → A7 (Demo)
A2 (Lifecycle) → A6 (Frontend buttons)
A3 (Browser room) → A6
A5 (Session writes) — independent
B4 needs A1-A4
B6 needs A1
B7 needs A5
B1, B2, B3, B5, B8 — independent
```
