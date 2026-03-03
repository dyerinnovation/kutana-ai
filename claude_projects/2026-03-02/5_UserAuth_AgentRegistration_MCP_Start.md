# Plan: User Auth, Agent Registration UI, MCP Server & Claude Agent SDK Agent

## Date: 2026-03-02

## Objective
Implement the full user auth + agent registration + MCP server + Claude Agent SDK agent milestone. This enables users to login via web UI, register agents with API keys, and have those agents connect to meetings via MCP tools.

## Blocks (in dependency order)
1. **Database Schema** — UserORM, AgentApiKeyORM, owner_id FK on AgentConfigORM
2. **Auth Utilities** — password hashing (bcrypt), JWT creation/validation, API key generation
3. **Auth API Routes** — register, login, /me endpoints
4. **Agent CRUD + API Keys** — Wire agents/meetings/tasks to DB, add API key CRUD + token exchange
5. **MCP Server** — FastMCP server with tools (list_meetings, join_meeting, get_transcript, etc.)
6. **Frontend Scaffold + Auth** — React + Vite + shadcn/ui, login/register pages
7. **Frontend Dashboard** — Agent management, API key generation, MCP config snippet
8. **Claude Agent SDK Example** — Meeting assistant agent using MCP tools
9. **Integration Testing** — Full-stack E2E test script

## Key Dependencies
- Blocks 1→2→3→4 are sequential (each depends on prior)
- Blocks 5 and 6-7 can run in parallel after Block 4
- Block 8 depends on Block 5
- Block 9 depends on all blocks

## Branch
`feature/user-auth-agent-registration-mcp`
