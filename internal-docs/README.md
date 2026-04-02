# Internal Docs

Contributor and maintainer documentation for Kutana AI. Not intended for end users.

For user-facing documentation see [`external-docs/`](../external-docs/README.md).

## Architecture

Implementation patterns, design decisions, and research:

- [`architecture/patterns/`](architecture/patterns/) — Claude Code / contributor reference patterns
  - `kutana-core.md` — domain models, events, interfaces, database
  - `provider-patterns.md` — ABC signatures, library conventions, registry
  - `message-bus.md` — MessageBus ABC, Redis Streams, MockMessageBus
  - `memory-architecture.md` — four-layer memory system
  - `service-patterns.md` — health endpoints, lifespan, settings, DI
  - `auth-and-api-keys.md` — JWT auth, API key system, token exchange
  - `mcp-server.md` — MCP tools, Streamable HTTP transport
  - `agent-gateway.md` — WebSocket gateway implementation
  - `uv-best-practices.md` — uv workspace patterns, testing commands
  - `pythonpath-workaround.md` — macOS UF_HIDDEN / .pth workaround
  - `dgx-spark-reference.md` — DGX hardware, K8s patterns, deployment
  - `dgx-spark-ssh.md` — SSH patterns, sudo, PATH, containerd
  - `git-best-practices.md` — contributor git workflow
- [`architecture/decisions/`](architecture/decisions/) — architectural decision records
  - `agent-platform-internals.md` — access matrix, auth flow, API key security
  - `pivot-recommendations.md` — strategic pivot history
  - `bootstrap-reference.md` — project bootstrap reference
  - `deepgram-integration.md` — Deepgram implementation details
- [`architecture/research/`](architecture/research/) — design exploration (8 files)

## Strategy

- [`strategy/roadmap.md`](strategy/roadmap.md) — implementation roadmap
- [`strategy/vision.md`](strategy/vision.md) — product vision and business case
- [`strategy/cost-architecture.md`](strategy/cost-architecture.md) — LLM/STT cost modeling
- [`strategy/competitive-analysis.md`](strategy/competitive-analysis.md) — competitive landscape
- [`strategy/go-to-market.md`](strategy/go-to-market.md) — launch and GTM strategy
- [`strategy/pivot-prompt.md`](strategy/pivot-prompt.md) — agent-first pivot context

## Development

- [`development/TASKLIST.md`](development/TASKLIST.md) — ordered task queue
- [`development/PROGRESS.md`](development/PROGRESS.md) — session-by-session progress log
- [`development/HANDOFF.md`](development/HANDOFF.md) — team transition context
- [`development/cowork-setup.md`](development/cowork-setup.md) — CoWork/CI scheduled task setup
- [`development/cowork-tasks/`](development/cowork-tasks/) — scheduled task definitions and output

## Infrastructure

- [`infrastructure/dgx-spark-setup-guide.md`](infrastructure/dgx-spark-setup-guide.md) — DGX K3s cluster setup
- [`infrastructure/agent-context-seeding.md`](infrastructure/agent-context-seeding.md) — context layer population

## Testing

- [`testing/test-plan-auth-mcp-frontend.md`](testing/test-plan-auth-mcp-frontend.md) — QA test strategy
- [`testing/milestone-playbooks/`](testing/milestone-playbooks/) — per-feature QA playbooks (00-SETUP through 10-full-e2e-demo)
- [`testing/manual/e2e-gateway-test.md`](testing/manual/e2e-gateway-test.md) — gateway + STT integration walkthrough
- [`testing/results/`](testing/results/) — QA test execution results
