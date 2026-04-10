# Active Issues

Scratchpad for bugs found, being fixed, or recently fixed. Not for planned work (use `shared-docs/development/TASKLIST.md`) and not for in-conversation todos (use TaskCreate).

---

## Open


### web-pod-f42dd99-not-deployed

- **Status:** open (fix committed, not deployed)
- **Found:** 2026-04-10, frontend smoke
- **Symptom:** Frontend envelope unwrap fix + data-testid attributes are committed but the running web pod still serves the old bundle.
- **Root cause:** Commit `f42dd99` was made by frontend-fixer but web image was not rebuilt+pushed+rolled out after that commit.
- **Fix:** pending — needs `/build-and-push web` + `kubectl rollout restart deploy/web`.
- **Notes:** Re-run both smoke tests after redeploy to confirm.

### activate-legacy-badrequest

- **Status:** won't-fix (dies with deprecated path)
- **Found:** 2026-04-10, phase-a7-iter-1
- **Symptom:** Deprecated `/activate` route throws BadRequestError.
- **Root cause:** Legacy code path replaced by checkbox-at-start flow.
- **Fix:** Route + calling UI (AgentsPage/AgentTemplatePage) will be removed in Phase A.7 cleanup.
- **Notes:** Not blocking. Keep here until the cleanup PR removes it.

---

## Recently Fixed

### start-warm-race-scenario-3

- **Status:** fixed (commit `47fdb7d`)
- **Found:** 2026-04-10, phase-a7-iter-1 smoke, scenario 3 only (scenarios 1 & 2 appeared to work due to timing variance — the commit could land before POST /start in lucky cases, making the race non-deterministic)
- **Symptom:** `POST /v1/meetings/{id}/start` silently skipped agent warming; reconciler backfilled at t≈33s.
- **Root cause:** `set_selected_agents` (PUT /selected-agents) only called `db.flush()`, not `db.commit()`. FastAPI's `yield`-dependency teardown commits AFTER the HTTP response is sent. With sub-ms intra-cluster RTT, `POST /start` can query `MeetingSelectedTemplateORM` before that transaction commits → sees 0 rows → creates no warming tasks, no log line emitted.
- **Fix:** `routes/meetings.py` `set_selected_agents`: added `await db.commit()` after `db.flush()`. Added `logger.info` in `start_meeting` for zero-selections case (defensive — valuable even after the fix to catch empty-selection meetings).
- **Commit:** `47fdb7d`

### frontend-envelope-array-mismatch

- **Status:** fixed (commit `f42dd99`, not yet on running pod — see open item `web-pod-f42dd99-not-deployed`)
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
