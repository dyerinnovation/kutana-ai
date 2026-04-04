# Weekly Architecture Review — Task Instructions

> These instructions are read and executed by the CoWork scheduled task.
> Runs every Friday at 4:00 PM.

---

## Process

1. Pull latest code:
   ```bash
   git pull origin main
   ```

2. Read the full project specification:
   ```
   Read CLAUDE.md thoroughly — this is the source of truth for all design principles.
   ```

3. Read the week's progress:
   ```
   Read docs/PROGRESS.md — focus on entries from the last 7 days.
   Read docs/TASKLIST.md — understand current phase and completion status.
   ```

4. Analyze the codebase:

   **a. Provider abstraction consistency**
   - Check every file in `packages/kutana-providers/` — do all implementations correctly extend the ABCs in `packages/kutana-core/src/kutana_core/interfaces/`?
   - Are there any direct imports of concrete providers in service code? (There shouldn't be — services should use the registry)
   - Are new providers registered in `registry.py`?

   **b. Event-driven architecture**
   - Check all inter-service communication — is it going through Redis Streams?
   - Are there any direct function calls between services? (Violation)
   - Are event definitions in `packages/kutana-core/src/kutana_core/events/definitions.py` up to date?

   **c. Async correctness**
   - Search for blocking calls in async code paths (`time.sleep`, synchronous DB calls, synchronous HTTP)
   - Verify all database operations use async SQLAlchemy
   - Check for proper `await` usage

   **d. Type safety**
   ```bash
   uv run mypy --strict . 2>&1 | tail -50
   ```

   **e. Test coverage**
   ```bash
   uv run pytest --tb=short -q 2>&1 | tail -30
   ```
   Identify modules with no test files.

   **f. Code organization**
   - Are Pydantic models in kutana-core and ORM models alongside their owning service?
   - Are there any business logic leaks into API route handlers?
   - File naming conventions (snake_case, proper module structure)

   **g. Dependency health**
   - Check pyproject.toml files for pinned vs. unpinned dependencies
   - Look for circular dependencies between packages

---

## Write the review

Overwrite `docs/cowork-tasks/cowork-task-output/WEEKLY_REVIEW.md` with:

```markdown
# Weekly Architecture Review — Week of {YYYY-MM-DD}

## Week Summary
{3-4 sentences: what was accomplished this week, which roadmap phases progressed,
overall trajectory}

## Architecture Compliance

### Provider Abstraction
- **Status:** {✅ Compliant / ⚠️ Minor issues / 🛑 Violations found}
- **Details:** {specific findings}

### Event-Driven Communication
- **Status:** {✅ Compliant / ⚠️ Minor issues / 🛑 Violations found}
- **Details:** {specific findings}

### Async Correctness
- **Status:** {✅ Compliant / ⚠️ Minor issues / 🛑 Violations found}
- **Details:** {specific findings}

### Type Safety
- **mypy results:** {error count and summary}
- **Problem areas:** {files or patterns that need attention}

### Test Coverage
- **Overall:** {X tests, Y passing, Z failing}
- **Gaps:** {modules or functions with no test coverage}

### Code Organization
- **Status:** {✅ Clean / ⚠️ Minor drift / 🛑 Significant issues}
- **Details:** {specific findings}

## Technical Debt Identified
{Numbered list of tech debt items found this week, ordered by severity}

1. {Description} — **Severity:** High/Medium/Low — **Suggested fix:** {brief}
2. ...

## Refactoring Priorities for Next Week
{Ordered list of what should be cleaned up before adding new features}

1. {Priority item and why}
2. ...

## ROADMAP.md Suggestions
{Any items that should be added, reordered, or broken into smaller pieces}

## Risk Register
{Things that could become problems if not addressed}

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| {description} | High/Med/Low | High/Med/Low | {suggested action} |
```

---

## Write to Obsidian vault

After writing `WEEKLY_REVIEW.md`, also copy the full report to the Obsidian vault:

Create `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Reports/weekly/{YYYY-MM-DD}.md` with the same content as the weekly review output.

**If the Obsidian vault is not mounted** (external SSD disconnected), skip the vault write and note the failure at the top of `WEEKLY_REVIEW.md`:
```
> Vault write skipped — /Volumes/Dev_SSD not mounted at time of run.
```

---

## Hard rules

- **Never modify code files.** This task is analysis only.
- **Be specific.** Reference exact file paths and line numbers when flagging issues.
- **Prioritize ruthlessly.** Not every finding needs immediate action — rank them.
- **Compare against CLAUDE.md, not personal preferences.** The project spec is the standard.
