# Convene AI

Agent-first meeting platform. AI agents connect via WebSocket; humans join via browser WebRTC. Agents are first-class participants — they listen for commitments, extract tasks, and maintain persistent memory across meetings.

## Architecture

Python monorepo (`uv` workspaces) + React 19 frontend.

**Packages:** `convene-core` (domain models) · `convene-providers` (STT/TTS/LLM) · `convene-memory` (4-layer memory)

**Services:** `api-server` · `audio-service` · `agent-gateway` · `mcp-server` · `task-engine` · `worker` · `cli` · `channel-server`

**Agent connection:** Claude Agent SDK → MCP Server (Bearer token) → Agent Gateway (WebSocket)

**Infra:** PostgreSQL 16 + pgvector · Redis 7 · LiveKit (WebRTC SFU) · Stripe billing · DGX Spark K3s cluster

## Current Phase

- **Phase 1** — Core AI Pipeline (in progress). STT wired, Redis Streams consumer implemented.
- **Phase 2** — Agent Platform (complete 2026-03-07). MCP OAuth 2.1, meeting lifecycle, browser room, templates, CLI, OpenClaw, channel routing.
- **Phase 3** — Meeting Platform. LiveKit WebRTC, video tiles, screen sharing, layout modes.

See `internal-docs/development/TASKLIST.md` for the task queue.

## Rules

@.claude/rules/architecture.md
@.claude/rules/python.md
@.claude/rules/frontend.md
@.claude/rules/git-workflow.md
@.claude/rules/security.md
@.claude/rules/documentation.md
@.claude/rules/dgx-connection.md

## Key References

- **Architecture patterns:** `internal-docs/architecture/patterns/` (core, providers, message-bus, memory, service-patterns, auth, mcp-server, uv, git)
- **Task queue:** `internal-docs/development/TASKLIST.md`
- **Roadmap & strategy:** `internal-docs/strategy/roadmap.md` · `internal-docs/strategy/cost-architecture.md`
- **Agent platform docs:** `external-docs/agent-platform/`
- **QA playbooks:** `internal-docs/testing/milestone-playbooks/`
- **CoWork setup:** `internal-docs/development/cowork-setup.md`

## Common Commands

```bash
# Run tests (on DGX)
ssh dgx 'cd ~/convene-ai && uv run pytest services/api-server/tests/'

# Build & push images
ssh dgx 'cd ~/convene-ai && bash scripts/build_and_push.sh all'

# Deploy
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm upgrade --install convene charts/convene -n convene'

# Pod status
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n convene'

# Frontend dev (local)
cd web && pnpm dev
```

## TASKLIST Lock Protocol

- **Start:** Add 🔒 to the item
- **Finish:** Replace `- [ ] 🔒` with `- [x]`
- Only the session that locked an item should unlock it
- **Milestone items (🏁)** — check off only when prerequisites pass
- **Phase change:** update `internal-docs/development/TASKLIST.md`, `CLAUDE.md`, and `external-docs/README.md`
