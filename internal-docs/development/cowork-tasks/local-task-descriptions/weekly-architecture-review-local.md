# Weekly Architecture Review — Local Desktop Task

> Local version. Runs Friday 4pm with full codebase access.

---

## Process

1. Pull latest:
   ```bash
   cd ~/Documents/dev/kutana-ai && git pull origin main
   ```

2. Read `CLAUDE.md` for conventions.

3. Perform comprehensive review:
   a) Provider abstraction — all providers extend ABCs, no direct imports in service code
   b) Event-driven communication — no cross-service imports
   c) Async correctness — no blocking calls in async functions
   d) Type safety — run `uv run mypy --strict .` if possible, check type: ignore comments
   e) Test coverage — count test files per package, identify zero-test packages
   f) Code organization — naming conventions, circular dependencies
   g) Tech debt — architectural violations, unresolved TODOs
   h) Security — hardcoded secrets, missing validation

4. Run quality checks:
   ```bash
   uv run ruff check .
   uv run pytest --tb=short -q
   ```

5. Compare against TASKLIST.md — check for items marked complete that may have regressed.

6. Write to Obsidian vault at `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Reports/weekly/{YYYY-MM-DD}.md`:

   ```markdown
   ---
   updated: {YYYY-MM-DD}
   type: weekly-review
   ---

   # Weekly Architecture Review — Week of {YYYY-MM-DD}

   ## Week Summary
   {2-3 paragraphs}

   ## Architecture Compliance
   {per-area findings}

   ## Quality Check Results
   {ruff, mypy, pytest results}

   ## Technical Debt
   {numbered, with severity, files, suggested fix, weeks carried forward}

   ## Risk Register
   | Risk | Likelihood | Impact | Mitigation |

   ## Recommendations
   {prioritized for next week}
   ```

7. Also overwrite `internal-docs/development/cowork-tasks/cowork-task-output/WEEKLY_REVIEW.md`.

---

## Hard rules

- Never modify code. Read-only analysis.
- Be thorough. This is the deepest review of the week.
- Track tech debt items across weeks with "carried forward N weeks" notation.
- Be honest about quality. Don't minimize issues.
