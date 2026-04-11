# Active Issues

Scratchpad for bugs found, being fixed, or recently fixed. Not for planned work (use `shared-docs/development/TASKLIST.md`) and not for in-conversation todos (use TaskCreate).

---

## Open

### agent-relay-tool-wait-race

- **Status:** open
- **Found:** 2026-04-10, phase-a7-iter-2 eval smoke, scenario 3 (`happy-path-standup`, meeting `85e401d7`)
- **Symptom:** Agent invoked `kutana_get_meeting_status` and `kutana_get_participants` tools. The relay then kept sending `user.message` transcript segments instead of `user.custom_tool_result`, triggering 16 × `BadRequestError: waiting on responses to events ... only user.tool_confirmation, user.custom_tool_result, or user.interrupt may be sent`. The session was stuck in tool-wait for the entire 20-segment window. Score regressed on scenario 3: 2.10 (iter-1) → 1.30 (iter-2).
- **Root cause:** `services/api-server/src/api_server/agent_lifecycle.py` transcript relay does not gate outbound events on the session's tool-wait state. Once the agent emits a tool_use, the relay must buffer user.message segments (or send them as user.custom_tool_result if that's semantically correct) until the tool result is delivered.
- **Fix:** pending
- **Notes:** Distinct from Phase A.6 notetaker prompt issue. This is the same error class as iter-1's `activate-legacy-badrequest` but now reproducing on the `/v1/meetings/{id}/start` path, so it's no longer confined to the deprecated `/activate` route. Likely blocking for any managed agent that uses tools mid-meeting (not just notetaker). Scenarios 1 and 2 probably only worked because those agents didn't call tools in the iter-2 run.

### activate-legacy-badrequest

- **Status:** won't-fix (dies with deprecated path)
- **Found:** 2026-04-10, phase-a7-iter-1
- **Symptom:** Deprecated `/activate` route throws BadRequestError.
- **Root cause:** Legacy code path replaced by checkbox-at-start flow.
- **Fix:** Route + calling UI (AgentsPage/AgentTemplatePage) will be removed in Phase A.7 cleanup.
- **Notes:** Not blocking. Keep here until the cleanup PR removes it.

---

## Recently Fixed

### langfuse-traces-never-landed

- **Status:** fixed (commit `8bfbb67`)
- **Found:** 2026-04-10
- **Symptom:** Langfuse UI showed no traces; SDK calls returned without error but nothing appeared.
- **Root cause:** Three compounding bugs in hand-written Helm templates: (1) ClickHouse migrations ran into `default` DB but `CLICKHOUSE_URL` pointed to `langfuse` DB — every UI query failed with "Unknown table expression 'traces'". (2) Missing `langfuse-worker` Deployment — v3 splits ingestion into web + worker; events sat in Redis/MinIO unprocessed. (3) Wrong image tag `langfuse/langfuse:3` (legacy v2 all-in-one). Two additional chart config bugs during migration to official chart: `CLICKHOUSE_MIGRATION_URL` had no credentials (go-migrate ignores separate env vars, requires creds in URL); `REDIS_PORT` NaN (Langfuse worker Zod schema validates it independently of `REDIS_CONNECTION_STRING`).
- **Fix:** Replace hand-written templates with official `langfuse-k8s` chart 1.5.25. Set `clickhouse.migration.url` with hex password embedded. Inject `REDIS_PORT` via `additionalEnv`. Rotate API keys. All 9 pods Running 1/1, health 200, `traces` table confirmed in ClickHouse.
- **Commit:** `8bfbb67`

### start-warm-race-scenario-3

- **Status:** fixed (commit `598a421`, deployed + verified iter-2 eval smoke)
- **Found:** 2026-04-10, phase-a7-iter-1 smoke, scenario 3 only (scenarios 1 & 2 appeared to work due to timing variance — the commit could land before POST /start in lucky cases, making the race non-deterministic)
- **Symptom:** `POST /v1/meetings/{id}/start` silently skipped agent warming; reconciler backfilled at t≈33s.
- **Root cause:** `set_selected_agents` (PUT /selected-agents) only called `db.flush()`, not `db.commit()`. FastAPI's `yield`-dependency teardown commits AFTER the HTTP response is sent. With sub-ms intra-cluster RTT, `POST /start` can query `MeetingSelectedTemplateORM` before that transaction commits → sees 0 rows → creates no warming tasks, no log line emitted.
- **Fix:** `routes/meetings.py` `set_selected_agents`: added `await db.commit()` after `db.flush()`. Added `logger.info` in `start_meeting` for zero-selections case (defensive — valuable even after the fix to catch empty-selection meetings).
- **Commit:** `598a421`
- **Verified:** iter-2 eval smoke — all 3 scenarios warmed via `/start` path in ~9.3–9.7s, no reconciler backfill.

### web-pod-f42dd99-not-deployed

- **Status:** fixed (deployed iter-2 task #1)
- **Found:** 2026-04-10, frontend smoke
- **Symptom:** Frontend envelope unwrap fix + data-testid attributes were committed but the running web pod still served the old bundle.
- **Root cause:** Commit `f42dd99` was made by iter-1 frontend-fixer but web image was not rebuilt+pushed+rolled out after that commit.
- **Fix:** iter-2 devops ran `/build-and-push web` + `kubectl rollout restart deploy/web`; new pod running `localhost:30500/kutana/web:latest` built from `f42dd99`.
- **Verified:** iter-2 frontend smoke (Playwright) — no React error boundary, checkboxes render, PUT /selected-agents fires with correct envelope, warming chips flip to ready <2s.

### frontend-envelope-array-mismatch

- **Status:** fixed (commit `f42dd99`, deployed + verified iter-2 frontend smoke)
- **Found:** 2026-04-10, frontend smoke
- **Symptom:** Backend returned `{meeting_id, selections}` but frontend typed as raw `SelectedAgent[]`. `.find()` crashed → React error boundary blocked all of `/meetings`.
- **Root cause:** Envelope/array type mismatch in `web/src/api/meetings.ts` (`getSelectedAgents`, `getAgentSessions`).
- **Fix:** commit `f42dd99` — unwrap `.selections` / `.sessions` from response envelope, added `data-testid` attributes.

### extractor-sdk-test-failures

- **Status:** fixed (commit `7159724`)
- **Found:** 2026-04-10, pre-existing (predates phase-a7-iter-1)
- **Symptom:** 3 failing tests in `packages/kutana-core/tests/test_extractor_sdk.py` (221/224 passing).
- **Root cause:** (1) `ExtractorValidationError.__init__` used `cls.__name__` unconditionally, masking validation errors; (2) two generated extractor source strings used `ClassVar` without importing it.
- **Fix:** commit `7159724` — `packages/kutana-core/src/kutana_core/extraction/loader.py` uses `getattr(cls, "__name__", repr(cls))`; test file adds `from typing import ClassVar` to two generated sources. 224/224 passing.

### web-pod-stale-15h

- **Status:** fixed mid-run
- **Found:** 2026-04-10, phase-a7-iter-1 smoke
- **Symptom:** Web pod 15h old during smoke; bundle missing commit `4476429`.
- **Root cause:** Deploy only built api-server; web pod not rebuilt.
- **Fix:** devops-2 ran `/build-and-push web` + `kubectl rollout restart deploy/web`; new pod from commit `7159724`.

### latest-tag-deploy-hiccups

- **Status:** worked around (logged as tech debt in TASKLIST.md under "Deploy / DevOps Tech Debt")
- **Found:** 2026-04-10
- **Symptom:** Stale eval Job blocked helm upgrade; `--set global.imageTag` broke unrelated services with ImagePullBackOff; `:latest` didn't trigger automatic rollout.
- **Root cause:** `:latest` tag + no rolling-update trigger + cross-service image tag coupling.
- **Fix:** deleted stale Job + plain helm upgrade + `kubectl rollout restart`. Proper fix tracked in TASKLIST.md.
