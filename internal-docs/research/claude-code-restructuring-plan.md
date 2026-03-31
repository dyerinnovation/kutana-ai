# Claude Code Restructuring Plan — Convene AI

**Date:** 2026-03-24
**Purpose:** Map current CLAUDE.md + claude_docs/ to Claude Code best practices; produce concrete migration plan with skill and rule recommendations.

---

## Executive Summary

The current setup has a 272-line CLAUDE.md (target: ≤200), 13 claude_docs/ reference files, and only one skill in `.claude/`. There are no rules files, no CI/CD hooks, and no operational/workflow skills. This plan restructures everything into the proper Claude Code layout: slim CLAUDE.md → `.claude/rules/` (always-loaded) → `.claude/skills/` (on-demand) → `claude_docs/` (detail references).

---

## Part 1: Current State Audit

### CLAUDE.md (272 lines)

| Section | Lines | Tag |
|---|---|---|
| Project Overview | ~5 | **CLAUDE.md** — keep |
| Architecture (packages/services/frontend/infra) | ~25 | **CLAUDE.md** — slim to structure only |
| Tech Stack & Conventions | ~12 | **RULE** → `python.md` / `frontend.md` |
| Key Design Principles | ~10 | **RULE** → `architecture.md` |
| Code Style | ~12 | **RULE** → `python.md` |
| File Naming | ~7 | **RULE** → `python.md` |
| Running Locally | ~14 | **SKILL** → `start-app` |
| Environment Variables | ~26 | **CLAUDE.md** — keep as reference block |
| Current Phase | ~4 | **CLAUDE.md** — keep (1 sentence each phase) |
| Git Workflow | ~8 | **RULE** → `git-workflow.md` |
| Documentation Requirements | ~8 | **RULE** → `documentation.md` |
| What NOT to Do | ~8 | **RULE** → distribute to `python.md`, `architecture.md` |
| Package Implementation Details refs | ~8 | **CLAUDE.md** — keep as @references |
| Agent Platform & Integrations refs | ~8 | **CLAUDE.md** — keep as @references |
| Tooling refs | ~3 | **CLAUDE.md** — keep as @references |
| Test Data | ~3 | **CLAUDE.md** — keep (1 line) |
| DGX Spark — SSH / compute / infra | ~45 | **RULE** → `dgx-connection.md` |
| LLM Strategy | ~5 | **RULE** → `architecture.md` |
| STT Strategy | ~4 | **RULE** → `architecture.md` |
| Billing Architecture | ~5 | **CLAUDE.md** — 2-sentence summary |
| CoWork Coordination | ~5 | **CLAUDE.md** — brief ref |
| TASKLIST Lock Protocol | ~5 | **RULE** → `git-workflow.md` |

**Result:** CLAUDE.md shrinks from 272 lines to ~130 lines.

---

### claude_docs/ Files (13 files)

| File | Contents | Tag |
|---|---|---|
| `Agent_Gateway_Architecture.md` | WebSocket protocol, message types, AudioBridge, domain models, 6 new events | **RULE reference** → keep in claude_docs/, @-ref from CLAUDE.md |
| `Auth_And_API_Keys.md` | JWT auth, API key system (cvn_ prefix), token exchange pattern | **RULE reference** → keep in claude_docs/, @-ref from security.md rule |
| `Convene_Core_Patterns.md` | Pydantic v2 patterns, enums, events, ORM patterns, session management | **RULE reference** → keep in claude_docs/, @-ref from python.md rule |
| `DGX_Spark_Reference.md` | Hardware specs, K3s cluster, kubectl/helm patterns, 11 gotchas | **RULE reference** → keep in claude_docs/, @-ref from dgx-connection.md rule |
| `DGX_Spark_SSH_Connection.md` | SSH alias, sudo patterns, sshpass, 5 gotchas, mDNS | **RULE reference** → keep in claude_docs/, @-ref from dgx-connection.md rule |
| `Git_Best_Practices.md` | Commit cadence, SSH setup, branch strategy, co-author trailer | **RULE reference** → keep in claude_docs/, @-ref from git-workflow.md rule |
| `MCP_Server_Architecture.md` | Streamable HTTP transport, 7 tools, resources, Docker setup | **RULE reference** → keep in claude_docs/, @-ref from CLAUDE.md |
| `Memory_Architecture.md` | Four-layer memory (Redis/PG/pgvector), ORM converters | **RULE reference** → keep in claude_docs/, @-ref from architecture.md rule |
| `MessageBus_Patterns.md` | ABC, Redis Streams impl, MockMessageBus, fan-out patterns | **RULE reference** → keep in claude_docs/, @-ref from architecture.md rule |
| `PYTHONPATH_Workaround.md` | macOS UF_HIDDEN fix, UV_LINK_MODE=copy | **RULE reference** → keep in claude_docs/, @-ref from python.md rule |
| `Provider_Patterns.md` | ABC signatures, third-party library conventions, registry | **RULE reference** → keep in claude_docs/, @-ref from architecture.md rule |
| `Service_Patterns.md` | Health endpoint, lifespan, settings, DI, route org | **RULE reference** → keep in claude_docs/, @-ref from python.md rule |
| `UV_Best_Practices.md` | uv add vs pip, workspace testing, pytest config, pitfalls | **RULE reference** → keep in claude_docs/, @-ref from python.md rule |

**Decision:** All 13 claude_docs/ files stay where they are. They become referenced via `@claude_docs/...` syntax in CLAUDE.md and rules files instead of inlined.

---

### .claude/ Current State

```
.claude/
├── settings.local.json     — Bash permissions (allow find for config files)
└── skills/
    └── convene-meeting/
        └── SKILL.md        — MCP meeting participation skill (good, keep)
```

**Missing:** No `rules/` directory. No operational skills. No hooks.

---

## Part 2: Before → After Mapping

### CLAUDE.md

| Current Location | After Migration |
|---|---|
| Tech Stack & Conventions section | → `.claude/rules/python.md` (Python) + `.claude/rules/frontend.md` (React) |
| Key Design Principles | → `.claude/rules/architecture.md` |
| Code Style rules | → `.claude/rules/python.md` |
| File Naming conventions | → `.claude/rules/python.md` |
| Running Locally commands | → `.claude/skills/start-app/SKILL.md` |
| Git Workflow section | → `.claude/rules/git-workflow.md` |
| Documentation Requirements | → `.claude/rules/documentation.md` |
| What NOT to Do (Python/uv) | → `.claude/rules/python.md` |
| What NOT to Do (architecture) | → `.claude/rules/architecture.md` |
| DGX Spark infra section (45 lines) | → `.claude/rules/dgx-connection.md` |
| LLM/STT strategy | → `.claude/rules/architecture.md` |
| TASKLIST Lock Protocol | → `.claude/rules/git-workflow.md` |
| Project overview + architecture structure | → stays in CLAUDE.md |
| Environment variables block | → stays in CLAUDE.md |
| Current Phase | → stays in CLAUDE.md |
| All @reference links | → stays in CLAUDE.md |

### claude_docs/ Files

All files **stay in place** — they become detail references rather than needing to be inlined. Rules files will `@reference` them for pinned context where relevant.

### New Files Created

```
.claude/
├── settings.json           — hooks config (pre/post tool)
├── settings.local.json     — existing (permissions)
├── rules/
│   ├── architecture.md     — ABC pattern, provider abstraction, event-driven
│   ├── git-workflow.md     — commit conventions, TASKLIST lock, branch names
│   ├── documentation.md    — docs-alongside-features, where to update
│   ├── dgx-connection.md   — SSH patterns, service URLs, DGX gotchas
│   ├── frontend.md         — React 19 + TS + Vite + Tailwind v4 (scoped: web/**)
│   ├── python.md           — Python 3.12+, ruff, mypy, uv (scoped: packages/**, services/**)
│   └── security.md         — JWT, input validation, rate limiting
└── skills/
    ├── convene-meeting/    — existing (keep)
    ├── start-app/
    ├── stop-app/
    ├── wipe-data/
    ├── test-user/
    ├── standup-demo/
    ├── deploy/
    ├── run-tests/
    ├── check-services/
    ├── new-feature/
    ├── new-mcp-tool/
    ├── merge-worktree/
    └── update-docs/
```

---

## Part 3: CI/CD Best Practices

### Claude Code Hooks

Hooks are defined in `.claude/settings.json` under the `hooks` key. They execute shell commands automatically in response to Claude Code events — **these run every session, not just manually**.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"Editing: $CLAUDE_TOOL_INPUT_FILE_PATH\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "cd /workspace && uv run ruff check --fix $CLAUDE_TOOL_INPUT_FILE_PATH 2>/dev/null || true"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Claude session ended' >> ~/.claude/session.log"
          }
        ]
      }
    ]
  }
}
```

#### Recommended Hooks for Convene AI

| Hook | Trigger | Command | Why |
|---|---|---|---|
| PostToolUse → Edit/Write | Python file edited | `uv run ruff check --fix <file>` | Auto-lint on every edit |
| PostToolUse → Edit/Write | Python file edited | `uv run ruff format <file>` | Auto-format on every edit |
| PostToolUse → Bash | Any bash command | log command for audit | Session audit trail |
| Stop | Session ends | Post summary to Discord | Visibility into what changed |
| PreToolUse → Bash | Commands with `DROP\|DELETE\|TRUNCATE` | Warn before destructive DB ops | Safety net |

#### Hook Environment Variables

When hooks fire, Claude Code exposes:
- `CLAUDE_TOOL_NAME` — which tool ran (e.g., `Edit`, `Bash`)
- `CLAUDE_TOOL_INPUT_*` — tool input fields (e.g., `CLAUDE_TOOL_INPUT_FILE_PATH`)
- `CLAUDE_TOOL_OUTPUT_*` — tool output

### GitHub Actions Integration

Claude Code supports non-interactive CI mode via `--print` and `--output-format` flags:

```yaml
# .github/workflows/claude-review.yml
name: Claude Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Claude Code PR Review
        uses: anthropics/claude-code-action@beta
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            Review the changes in this PR for:
            1. Python type hints (mypy strict compliance)
            2. Missing tests for new public methods
            3. ABC pattern violations (direct provider instantiation)
            4. Security issues (unvalidated input, missing auth checks)
            Output a concise review as GitHub PR comments.
```

#### Claude Code in CI (Manual Invocation)

```bash
# Non-interactive mode — print output and exit
claude --print "Run the test suite and report failures" \
  --output-format json \
  --no-interactive

# With specific model
claude --model claude-sonnet-4-6 --print "Check for ruff errors in services/"
```

#### Recommended GitHub Actions Workflows

1. **PR Review** — Auto-review PRs for architecture violations, missing types, missing tests
2. **Docs Check** — On merge to main, verify TASKLIST and ROADMAP reflect completed features
3. **Security Scan** — On new API endpoints, check for missing auth, rate limiting, input validation
4. **Migration Linter** — Before DB migration deploy, Claude reviews the Alembic migration file

### Automated Testing with Claude Code

```bash
# Run in CI to generate a test report
claude --print "Run: cd /workspace && UV_LINK_MODE=copy uv run pytest packages/ services/ -x --tb=short" \
  --allowedTools "Bash" \
  --output-format text

# Interpret test failures and suggest fixes
claude --print "Tests failed. Read the output above and propose the minimal fix for each failure."
```

### DGX Deployment Automation

Since Convene runs on DGX Spark K3s, the deploy pattern is:

```bash
# In CI or on-demand via skill
ssh dgx 'cd ~/convene-ai && git pull && echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout restart deployment -n convene'
```

---

## Part 4: Recommended Skills

Skills live in `.claude/skills/<skill-name>/SKILL.md`. Users invoke with `/skill-name`.

---

### Operational Skills (Human-invocable)

#### `/start-app`
**Purpose:** Start all Convene services on DGX.

```markdown
# start-app

Start all Convene AI services on the DGX Spark cluster.

## Steps

1. Check current pod status:
   ```
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n convene'
   ```

2. If using docker compose (dev mode):
   ```
   ssh dgx 'cd ~/convene-ai && docker compose up -d'
   ```

3. If using K3s (production mode):
   ```
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout restart deployment -n convene'
   ```

4. Wait for pods to be Running (poll every 5s, timeout 120s):
   ```
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout status deployment -n convene --timeout=120s'
   ```

5. Run health checks via /check-services skill to verify.

## Expected Output
All pods in `Running` state. Health endpoints returning 200.
```

---

#### `/stop-app`
**Purpose:** Shut down all Convene services cleanly.

```markdown
# stop-app

Shut down all Convene AI services on DGX Spark.

## Steps

1. Scale all deployments to 0 (preserves config):
   ```
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl scale deployment --all --replicas=0 -n convene'
   ```

2. Or if using docker compose:
   ```
   ssh dgx 'cd ~/convene-ai && docker compose down'
   ```

3. Confirm pods terminated:
   ```
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n convene'
   ```
   Expected: No pods or all in `Terminating` → `none`.
```

---

#### `/wipe-data`
**Purpose:** Reset database and Redis to clean state for testing.

```markdown
# wipe-data

⚠️  DESTRUCTIVE — wipes all meeting data, tasks, transcripts, and Redis state.

**Confirm with user before running.** Only for dev/test environments.

## Steps

1. Stop services first (run /stop-app).

2. Drop and recreate the database:
   ```
   ssh dgx 'cd ~/convene-ai && docker compose exec postgres psql -U convene -c "DROP DATABASE convene;" && docker compose exec postgres psql -U convene -c "CREATE DATABASE convene;"'
   ```

3. Re-run migrations:
   ```
   ssh dgx 'cd ~/convene-ai && uv run alembic upgrade head'
   ```

4. Flush Redis:
   ```
   ssh dgx 'docker compose exec redis redis-cli FLUSHALL'
   ```

5. Restart services (/start-app).

## Verification
- Postgres: 0 rows in meetings, tasks, participants tables
- Redis: DBSIZE returns 0
```

---

#### `/test-user`
**Purpose:** Show or create a test user with known credentials.

```markdown
# test-user

Show existing test user credentials or create a new test user.

## Check for Existing Test User

```bash
ssh dgx 'cd ~/convene-ai && uv run python -c "
import asyncio
from services.api_server.database import get_session
from services.api_server.models.user import UserORM
asyncio.run(main())
"'
```

## Create Test User via API

```bash
# Register
curl -s -X POST http://convene.spark-b0f2.local/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@convene.local","password":"TestPass123!","full_name":"Test User"}'

# Login and get token
curl -s -X POST http://convene.spark-b0f2.local/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@convene.local","password":"TestPass123!"}' | jq .access_token
```

## Default Test Credentials
- Email: `test@convene.local`
- Password: `TestPass123!`
- API Key: Generate via `POST /api/v1/api-keys` after login
```

---

#### `/standup-demo`
**Purpose:** Launch the 3-person standup demo (Business Bot + Coding Bot).

```markdown
# standup-demo

Launch the Convene AI 3-person standup demo: 1 human + Business Bot + Coding Bot.

## Prerequisites
- Services running (/start-app)
- Test user available (/test-user)
- MCP server accessible at https://convene.spark-b0f2.local/mcp

## Steps

1. Create a standup meeting:
   ```bash
   curl -X POST http://convene.spark-b0f2.local/api/v1/meetings \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"title":"Standup Demo","meeting_type":"standup"}'
   ```
   Note the `meeting_id`.

2. Connect Business Bot (MCP agent with listen+extract capabilities):
   ```bash
   cd examples/meeting-assistant-agent
   AGENT_TEMPLATE=business uv run python main.py --meeting-id $MEETING_ID
   ```

3. Connect Coding Bot (MCP agent with voice+tts capabilities):
   ```bash
   AGENT_TEMPLATE=coding uv run python main.py --meeting-id $MEETING_ID
   ```

4. Human joins via browser at:
   ```
   https://convene.spark-b0f2.local/meetings/$MEETING_ID
   ```

5. Verify in logs:
   - Transcripts flowing via `GET /api/v1/meetings/$MEETING_ID/transcript`
   - Tasks being extracted via `GET /api/v1/meetings/$MEETING_ID/tasks`

## Expected Outcome
3 participants shown in UI. Transcript visible. Tasks extracted within ~10s of commitment utterances.
```

---

#### `/deploy`
**Purpose:** Pull latest, rebuild, restart services on DGX.

```markdown
# deploy

Deploy the latest code to DGX Spark.

## Steps

1. Sync code to DGX:
   ```bash
   rsync -avz --exclude='.venv' --exclude='node_modules' --exclude='.git' \
     /Users/jonathandyer/Documents/Dyer_Innovation/dev/convene-ai/ \
     dgx:~/convene-ai/
   ```

2. Or if already committed, pull on DGX:
   ```bash
   ssh dgx 'cd ~/convene-ai && git pull origin main'
   ```

3. Rebuild Python packages:
   ```bash
   ssh dgx 'cd ~/convene-ai && UV_LINK_MODE=copy uv sync'
   ```

4. Run DB migrations:
   ```bash
   ssh dgx 'cd ~/convene-ai && uv run alembic upgrade head'
   ```

5. Rebuild and restart services:
   ```bash
   # Docker compose
   ssh dgx 'cd ~/convene-ai && docker compose build && docker compose up -d'

   # OR K3s (if image-based)
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout restart deployment -n convene'
   ```

6. Verify (/check-services).

## Notes
- Always run migrations before restarting services
- If schema changed, /wipe-data may be needed in dev
```

---

#### `/run-tests`
**Purpose:** Run the full test suite (pytest + vitest).

```markdown
# run-tests

Run the complete Convene AI test suite on DGX.

## Python Tests (pytest)

```bash
# All packages and services
ssh dgx 'cd ~/convene-ai && UV_LINK_MODE=copy uv run pytest packages/ services/ -x --tb=short -q'

# Specific package
ssh dgx 'cd ~/convene-ai && UV_LINK_MODE=copy uv run pytest packages/convene-core/ -x --tb=short'

# With coverage
ssh dgx 'cd ~/convene-ai && UV_LINK_MODE=copy uv run pytest packages/ services/ --cov=src --cov-report=term-missing'
```

## Frontend Tests (vitest)

```bash
ssh dgx 'cd ~/convene-ai/web && npm run test'
```

## Type Checking

```bash
ssh dgx 'cd ~/convene-ai && uv run mypy packages/ services/ --ignore-missing-imports'
```

## Lint Check

```bash
ssh dgx 'cd ~/convene-ai && uv run ruff check packages/ services/'
```

## Expected Pass Criteria
- All pytest tests green
- No mypy errors (strict mode)
- No ruff violations
- Vitest all passing
```

---

#### `/check-services`
**Purpose:** Health check all running services.

```markdown
# check-services

Check health of all Convene AI services.

## K3s Pod Status

```bash
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n convene -o wide'
```

## HTTP Health Endpoints

```bash
# API Server
curl -s http://convene.spark-b0f2.local/api/v1/health | jq .

# Agent Gateway
curl -s http://convene.spark-b0f2.local:8003/health | jq .

# MCP Server
curl -s https://convene.spark-b0f2.local/mcp/health | jq .

# Audio Service
curl -s http://convene.spark-b0f2.local:8002/health | jq .
```

## Redis Check

```bash
ssh dgx 'docker compose exec redis redis-cli ping'
# Expected: PONG
```

## Postgres Check

```bash
ssh dgx 'docker compose exec postgres psql -U convene -c "SELECT 1"'
# Expected: 1 row
```

## Log Tailing

```bash
# All services
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl logs -n convene -l app=api-server --tail=20'
```

## Expected: All green
- All pods: `Running` (1/1 or 2/2)
- All health endpoints: `{"status": "ok"}`
- Redis: `PONG`
- Postgres: `1`
```

---

### Agent Workflow Skills (Used during development)

#### `/new-feature`
**Purpose:** Scaffold a new feature following the ABC pattern.

```markdown
# new-feature

Scaffold a new Convene AI feature following the provider abstraction pattern.

## Required Inputs
- Feature name (snake_case): e.g., `calendar_sync`
- Package it belongs to: e.g., `convene-core`, `convene-providers`, or a service
- Provider type (if applicable): e.g., `CalendarProvider`

## Steps

### 1. Define the Abstract Interface (convene-core)
Create `packages/convene-core/src/convene_core/interfaces/<feature>.py`:
```python
from abc import ABC, abstractmethod

class <Name>Provider(ABC):
    @abstractmethod
    async def <method>(self, ...) -> ...: ...
```

### 2. Define Domain Models
Add to `packages/convene-core/src/convene_core/models/<feature>.py`:
- Pydantic v2 models with `from __future__ import annotations`
- Enums as `str, Enum`
- UTC timestamps with `default_factory=lambda: datetime.now(UTC)`

### 3. Create First Implementation (convene-providers)
Create `packages/convene-providers/src/convene_providers/<feature>/<provider_name>.py`:
- Implement all abstract methods
- Use async I/O only

### 4. Register in Provider Registry
Add to `packages/convene-providers/src/convene_providers/registry.py`.

### 5. Add ORM Model (if persisted)
Create migration: `uv run alembic revision --autogenerate -m "add_<feature>"`

### 6. Write Tests
- `packages/convene-core/tests/test_<feature>_models.py`
- `packages/convene-providers/tests/test_<provider>_<feature>.py` (mock external calls)

### 7. Update TASKLIST
- Mark the relevant task `- [x]` in `docs/TASKLIST.md`
- Add any new sub-tasks that emerged

### 8. Update Docs
- Add section to relevant `docs/technical/` page
- Update `CLAUDE.md` if a new package reference is needed

## Pattern Reference
See @claude_docs/Convene_Core_Patterns.md and @claude_docs/Provider_Patterns.md
```

---

#### `/new-mcp-tool`
**Purpose:** Add a new MCP tool to the MCP server.

```markdown
# new-mcp-tool

Add a new tool to the Convene MCP server.

## Required Inputs
- Tool name (snake_case): e.g., `get_action_items`
- Description (1 sentence for Claude to understand when to use it)
- Input schema (params + types)
- Output schema (what it returns)

## Steps

### 1. Add Tool Handler
In `services/mcp-server/src/mcp_server/tools/<tool_name>.py`:
```python
async def handle_<tool_name>(params: dict) -> dict:
    """<Description>"""
    ...
```

### 2. Register in MCP Server
Add to `services/mcp-server/src/mcp_server/main.py`:
```python
@server.tool("<tool_name>")
async def <tool_name>(params: ...) -> ...:
    return await handle_<tool_name>(params)
```

### 3. Write Tests
`services/mcp-server/tests/test_<tool_name>.py` — mock the API calls.

### 4. Update OpenClaw Plugin
Add the tool to `integrations/openclaw-plugin/convene_tools.json`.

### 5. Update MCP Architecture Docs
Add entry to `claude_docs/MCP_Server_Architecture.md` tool table.

### 6. Update TASKLIST
Mark task done in `docs/TASKLIST.md`.

## Reference
See @claude_docs/MCP_Server_Architecture.md
```

---

#### `/merge-worktree`
**Purpose:** Merge a worktree branch into main and push.

```markdown
# merge-worktree

Merge the current Claude Code worktree branch into main and push.

## Steps

### 1. Check current branch and status
```bash
git branch --show-current
git status
git log --oneline -5
```

### 2. Ensure all changes are committed
If there are uncommitted changes, commit them:
```bash
git add <specific files>
git commit -m "type: description

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### 3. Switch to main and pull latest
```bash
git checkout main
git pull origin main
```

### 4. Merge the worktree branch
```bash
git merge --no-ff claude/<worktree-name> -m "Merge branch 'claude/<worktree-name>' — <feature description>"
```

### 5. Push to remote (SSH)
```bash
git push origin main
```

### 6. Verify on remote
```bash
git log --oneline -3
```

### 7. Clean up worktree (from main repo)
```bash
git worktree remove .claude/worktrees/<worktree-name>
git branch -d claude/<worktree-name>
```

## Notes
- Use SSH remote (`git@github.com:dyerinnovation/convene-ai.git`) — HTTPS hangs
- If push hangs, split commits and push in smaller batches
- See @claude_docs/Git_Best_Practices.md for full patterns
```

---

#### `/update-docs`
**Purpose:** After a feature lands, update all relevant documentation.

```markdown
# update-docs

After a feature merges, update all documentation to reflect the completed work.

## Checklist

### 1. TASKLIST.md
- [ ] Mark the feature task `- [x]` (remove 🔒 if locked)
- [ ] Check if any milestone (🏁) can now be checked off
- [ ] Add any new follow-on tasks discovered

### 2. ROADMAP.md
- [ ] Move feature from "In Progress" to "Completed" if applicable
- [ ] Update "Current Phase" if a phase is complete

### 3. Technical Docs (`docs/technical/`)
- [ ] Update or create the relevant architecture doc page
- [ ] Update API endpoint docs if new endpoints were added
- [ ] Update sequence diagrams if flow changed

### 4. CLAUDE.md
- [ ] Update "Current Phase" line if phase changed
- [ ] Add new @reference if a new claude_docs file was created

### 5. claude_docs/
- [ ] Update the relevant pattern doc if new patterns were introduced
- [ ] Add new file if this introduces a significantly new subsystem

### 6. Service/Package README
- [ ] Update the README in the affected `services/<name>/` or `packages/<name>/` directory

### 7. CoWork Task Descriptions
- [ ] Update `docs/cowork-tasks/` if the feature changes scheduled task behavior

## After Completing
Commit all doc changes together:
```bash
git add docs/ claude_docs/ CLAUDE.md
git commit -m "docs: update documentation for <feature>

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
```

---

## Part 5: Recommended Rules

Rules in `.claude/rules/` are **always loaded** into Claude's context. They can be scoped by path (using `globs` frontmatter) so language-specific rules only fire for relevant files.

---

### `architecture.md`

```markdown
---
# No globs — applies to all files
---

# Architecture Rules

## Provider Abstraction (ABC-First)
Every external service integration MUST have an abstract base class in convene-core before any implementation:
1. Define ABC in `packages/convene-core/src/convene_core/interfaces/<name>.py`
2. Implement in `packages/convene-providers/src/convene_providers/<name>/`
3. Register in `packages/convene-providers/src/convene_providers/registry.py`
Never import a concrete provider directly in business logic — always resolve via registry.

## Event-Driven Between Services
Services communicate via Redis Streams events, never direct HTTP calls to each other.
- Publisher: `message_bus.publish(topic, event.to_dict())`
- Consumer: `message_bus.subscribe(topic, handler)`
See @claude_docs/MessageBus_Patterns.md

## Memory Architecture
Four layers — use the right layer for the right data:
- Working memory (Redis): ephemeral meeting state, active speakers
- Short-term (Postgres): meeting records, tasks, participants
- Long-term (pgvector): embeddings for semantic search
- Structured (Postgres): indexed queries, action items by meeting
See @claude_docs/Memory_Architecture.md

## LLM Tiers
- Haiku: entity extraction (high volume)
- Sonnet: recaps, agent dialogue
- Opus: premium analysis (Business/Enterprise only)
Never use OpenAI or Google models — Claude API only.

## STT Provider
Primary: Deepgram Nova-2. Self-hosted faster-whisper is Enterprise-only.
All STT must go through the STTProvider ABC.
See @claude_docs/Provider_Patterns.md
```

---

### `git-workflow.md`

```markdown
---
# No globs — applies everywhere
---

# Git Workflow Rules

## Commit Cadence
- Commit and push after each plan/feature completes — do not accumulate changes
- Keep commits small and focused on a single logical change
- Large commits (100+ files) can hang on push — batch by area

## Commit Message Format
```
type: short description (under 72 chars)

Optional body.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```
Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `infra`

## Branch Naming
- Feature branches: `feat/<description>` or `claude/<worktree-name>`
- Scheduled: `scheduled/<date>-<description>`

## Remote: SSH Only
Use `git@github.com:dyerinnovation/convene-ai.git` — HTTPS hangs in non-interactive shells.
SSH key: `~/.ssh/dyerinnovation-key`

## TASKLIST Lock Protocol
- When starting a TASKLIST item: add 🔒 to prevent other sessions picking it up
- When finishing: replace `- [ ] 🔒` with `- [x]`
- Never unlock an item you didn't lock
- Milestone items (🏁) are verification checkpoints — check off when prerequisites pass

## Merge Worktrees
Use `/merge-worktree` skill for consistent worktree merge process.
See @claude_docs/Git_Best_Practices.md
```

---

### `documentation.md`

```markdown
---
# No globs — applies everywhere
---

# Documentation Rules

## Docs Alongside Features
Documentation updates MUST be committed alongside feature code — never as separate follow-up commits.

For every feature, update:
1. `docs/TASKLIST.md` — mark task done
2. `docs/ROADMAP.md` — if phase-level change
3. `docs/technical/<relevant>.md` — architecture/API docs
4. Service/package README in the affected directory
5. `claude_docs/` — if new patterns are introduced

## What Goes Where
- **CLAUDE.md** — project overview, current phase, key references only (stay under 200 lines)
- **claude_docs/** — detailed implementation patterns, reference docs
- **docs/technical/** — human-facing technical docs (architecture, API, design decisions)
- **docs/integrations/** — third-party integration guides
- **.claude/rules/** — always-loaded coding standards
- **.claude/skills/** — repeatable procedures and workflows

## Phase Change Rule
When changing phase numbers, update ALL THREE: `docs/TASKLIST.md`, `CLAUDE.md`, and `docs/README.md`.

## New Subsystem Rule
New service or package → new README.md in that directory.
New architecture pattern → new file in `claude_docs/`.
```

---

### `dgx-connection.md`

```markdown
---
# No globs — applies everywhere (infrastructure commands)
---

# DGX Spark Connection Rules

## SSH Patterns
All heavy compute, Docker builds, and container workloads run on DGX Spark.

Regular commands (no password):
```bash
ssh dgx '<command>'
scp local-file.txt dgx:~/path/
rsync -avz --exclude='.venv' ./local/ dgx:~/remote/
```

Sudo commands (pipe password — single quotes prevent ! expansion):
```bash
ssh dgx 'echo JDf33nawm3! | sudo -S <command>'
```

kubectl (must pass KUBECONFIG explicitly — sudo drops env vars):
```bash
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -A'
```

helm (full path — not in sudo PATH):
```bash
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm list -A'
```

## Service URLs (K3s Cluster)
- Frontend + API: `https://convene.spark-b0f2.local`
- MCP Server: `https://convene.spark-b0f2.local/mcp`
- Agent Gateway: `ws://spark-b0f2.local:8003`
- STT (Whisper): `http://spark-b0f2.local/convene-stt`

## Critical Gotchas
- Container runtime is `containerd` (not Docker) — import via `sudo k3s ctr images import <file>`
- Use `aiohttp` (not `httpx`) for mDNS HTTP — httpx hangs on IPv6/mDNS resolution
- DGX is ARM64 (aarch64) — build images for `linux/arm64`
- Non-interactive SSH won't source `.bashrc` — PATH is `$HOME/.local/bin:$HOME/.nvm/versions/node/v22.22.0/bin:$PATH`
- NEVER run Docker builds or container workloads on the personal Mac

See @claude_docs/DGX_Spark_SSH_Connection.md and @claude_docs/DGX_Spark_Reference.md
```

---

### `frontend.md` (scoped to web/**)

```markdown
---
globs: ["web/**/*.ts", "web/**/*.tsx", "web/**/*.css", "web/**/*.html"]
---

# Frontend Rules (web/**)

## Stack
- React 19 (not 18) — use new hooks and concurrent features
- TypeScript strict mode — no `any` without comment
- Vite for bundling
- Tailwind v4 (not v3) — use CSS variables and `@theme` directive, not `tailwind.config.js`

## Component Conventions
- Functional components only — no class components
- Co-locate component styles with component (Tailwind classes, no separate CSS files)
- Props interfaces use TypeScript `interface`, not `type` (for extensibility)
- File names: PascalCase for components (`MeetingRoom.tsx`), camelCase for utils

## State Management
- React built-in state for local/component state
- Context API for cross-component shared state
- No Redux — keep it simple

## API Calls
- Use the generated API client from the OpenAPI spec
- Always handle loading, error, and success states
- Never make direct fetch() calls — go through the API client layer

## Testing
- Vitest for unit/component tests
- Co-locate test files: `ComponentName.test.tsx`
- Mock API calls — never hit real backend in unit tests
```

---

### `python.md` (scoped to packages/** and services/**)

```markdown
---
globs: ["packages/**/*.py", "services/**/*.py"]
---

# Python Rules (packages/** and services/**)

## Language & Runtime
- Python 3.12+ features are available — use them
- `from __future__ import annotations` at top of all files
- Type hint every function signature and return value — no exceptions

## Package Management (uv — strict rules)
- `uv add <package>` to add dependencies (NEVER `pip install`)
- `uv add --dev <package>` for dev deps
- `uv run pytest` to run tests
- NEVER use `uv pip install` — only `uv add` / `uv sync`
- UV_LINK_MODE=copy for test runs on macOS APFS

## Linting & Formatting
- `ruff check --fix` and `ruff format` — replaces black, isort, flake8
- `mypy` in strict mode — no `# type: ignore` without explanation comment
- Run before every commit

## Async
- `async def` for all I/O operations
- No blocking calls in async code paths
- Use `asyncio` throughout — no threading for I/O

## Pydantic v2
- All API models use Pydantic v2 with `model_validator` and `field_validator`
- Enums as `class Foo(str, Enum)` for JSON serialization
- UTC timestamps: `default_factory=lambda: datetime.now(UTC)`
See @claude_docs/Convene_Core_Patterns.md

## SQLAlchemy 2.0
- Async style with `mapped_column` and `Mapped[]` type hints
- UUID primary keys with `server_default=text("gen_random_uuid()")`
- Never use synchronous session in async context
See @claude_docs/Convene_Core_Patterns.md

## Testing
- pytest with `asyncio_mode=auto` and `--import-mode=importlib`
- Tests in `tests/` directory within each package/service
- Mock all external calls — never hit real network in unit tests

## What NOT to Do
- No Poetry or pip — uv only
- No synchronous database calls — always async SQLAlchemy
- No business logic in API endpoints — use service layer functions
- No platform-specific meeting SDKs (Zoom, Teams) — agents connect via agent-gateway
See @claude_docs/UV_Best_Practices.md, @claude_docs/PYTHONPATH_Workaround.md, @claude_docs/Service_Patterns.md
```

---

### `security.md`

```markdown
---
# No globs — security applies everywhere
---

# Security Rules

## Every New API Endpoint Must Have
1. **Authentication** — `get_current_user()` dependency (or explicit public route justification)
2. **Authorization** — check resource ownership before returning data
3. **Input validation** — Pydantic model for all request bodies; never `request.json()` directly
4. **Rate limiting** — apply rate limit decorator to all public/auth endpoints

## JWT Scopes
- Check scopes in every protected endpoint handler
- Agent gateway tokens have narrower scope than user JWTs
- Never issue tokens without expiry
See @claude_docs/Auth_And_API_Keys.md

## API Keys
- API keys stored SHA-256 hashed — never store plaintext
- `cvn_` prefix for all Convene API keys
- Keys scoped to specific capabilities (listen, speak, extract_tasks, etc.)

## WebSocket Security
- Validate JWT on WebSocket upgrade (before accepting connection)
- Drop connection on first invalid message (don't retry auth)

## Secrets
- All secrets via environment variables — never hardcoded
- Never log secrets, tokens, or API keys
- `.env` files never committed to git

## Input Validation Anti-Patterns
- No `eval()`, `exec()`, or dynamic SQL string building
- No direct OS command execution from user input
- Sanitize meeting titles and user names before storing
```

---

## Part 6: Concrete Migration Plan

### Step 1: Create `.claude/rules/` directory and rule files

```bash
mkdir -p .claude/rules
```

Create each rule file from the templates in Part 5:
- `.claude/rules/architecture.md`
- `.claude/rules/git-workflow.md`
- `.claude/rules/documentation.md`
- `.claude/rules/dgx-connection.md`
- `.claude/rules/frontend.md` (with `globs: ["web/**/*.ts", ...]`)
- `.claude/rules/python.md` (with `globs: ["packages/**/*.py", "services/**/*.py"]`)
- `.claude/rules/security.md`

### Step 2: Create `.claude/skills/` directories for 12 new skills

```bash
mkdir -p .claude/skills/{start-app,stop-app,wipe-data,test-user,standup-demo,deploy,run-tests,check-services,new-feature,new-mcp-tool,merge-worktree,update-docs}
```

Create `SKILL.md` in each from templates in Part 4.

### Step 3: Slim CLAUDE.md to under 200 lines

Remove from CLAUDE.md:
- [ ] Tech Stack & Conventions section → consolidated into rules
- [ ] Code Style section → into `python.md` rule
- [ ] File Naming section → into `python.md` rule
- [ ] Running Locally section → into `start-app` skill
- [ ] Git Workflow section → into `git-workflow.md` rule
- [ ] Documentation Requirements section → into `documentation.md` rule
- [ ] What NOT to Do section → distributed into rules
- [ ] DGX Spark infrastructure section (45 lines) → into `dgx-connection.md` rule
- [ ] LLM/STT/Billing detail paragraphs → keep 1-sentence summaries

Keep in CLAUDE.md:
- [ ] Project Overview (3-5 sentences)
- [ ] Architecture structure (package/service listing)
- [ ] Environment variables block (needed for quick reference)
- [ ] Current Phase (1-2 sentences per phase)
- [ ] All @reference links to claude_docs/

### Step 4: Configure hooks in `.claude/settings.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "FILE=$CLAUDE_TOOL_INPUT_FILE_PATH; if [[ \"$FILE\" == *.py ]]; then cd /Users/jonathandyer/Documents/Dyer_Innovation/dev/convene-ai && uv run ruff check --fix \"$FILE\" 2>/dev/null && uv run ruff format \"$FILE\" 2>/dev/null; fi"
          }
        ]
      }
    ]
  }
}
```

> Note: Test hook carefully — `CLAUDE_TOOL_INPUT_FILE_PATH` is the variable name but verify exact env var name in current Claude Code version.

### Step 5: Update CLAUDE.md @references

Ensure CLAUDE.md includes @references to all relevant claude_docs files:

```markdown
## Key References
- Architecture patterns: @claude_docs/Convene_Core_Patterns.md
- Provider patterns: @claude_docs/Provider_Patterns.md
- Message bus: @claude_docs/MessageBus_Patterns.md
- Memory system: @claude_docs/Memory_Architecture.md
- Service patterns: @claude_docs/Service_Patterns.md
- Agent gateway: @claude_docs/Agent_Gateway_Architecture.md
- MCP server: @claude_docs/MCP_Server_Architecture.md
- Auth & API keys: @claude_docs/Auth_And_API_Keys.md
- DGX Spark SSH: @claude_docs/DGX_Spark_SSH_Connection.md
- DGX Spark reference: @claude_docs/DGX_Spark_Reference.md
- Git workflow: @claude_docs/Git_Best_Practices.md
- uv best practices: @claude_docs/UV_Best_Practices.md
- PYTHONPATH workaround: @claude_docs/PYTHONPATH_Workaround.md
```

### Step 6: Verify Claude Code picks up new structure

After migration, start a new Claude Code session and verify:

```bash
# Claude Code shows rules are loaded
claude --print "What rules and skills are available?" --allowedTools ""
```

Expected: Claude should reference the architecture, git-workflow, python, etc. rules in its responses. Skills should be listed and invocable via `/skill-name`.

### Step 7: Validate rules are scoped correctly

Test that path-scoped rules fire:
1. Open a Python file — confirm `python.md` rule context is active
2. Open a TypeScript file in `web/` — confirm `frontend.md` rule is active but `python.md` is not

### Step 8: Commit and push

```bash
git add .claude/rules/ .claude/skills/ CLAUDE.md
git commit -m "chore: restructure Claude Code config — rules, skills, slim CLAUDE.md

- Add 7 always-loaded rules (.claude/rules/)
- Add 12 operational + workflow skills (.claude/skills/)
- Slim CLAUDE.md from 272 to ~130 lines
- Configure PostToolUse hooks for auto-linting

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
git push origin main
```

---

## Appendix: File Size Targets After Migration

| File | Before | After |
|---|---|---|
| `CLAUDE.md` | 272 lines | ~130 lines |
| `.claude/rules/` | 0 files | 7 files (~200 lines each) |
| `.claude/skills/` | 1 skill | 13 skills |
| `claude_docs/` | 13 files | 13 files (unchanged) |
| `.claude/settings.json` | absent | 1 file (hooks) |

## Appendix: Claude Code Rules vs Skills Decision Criteria

| Type | Use for... |
|---|---|
| **Rule** (always loaded) | Coding standards, architectural patterns, workflow conventions — things Claude should always follow |
| **Skill** (on-demand) | Operational procedures, multi-step workflows, things invoked explicitly |
| **CLAUDE.md** | Project overview, current state, key references — what every session needs |
| **claude_docs/** | Detailed reference docs — too long to always-load, referenced explicitly when needed |
