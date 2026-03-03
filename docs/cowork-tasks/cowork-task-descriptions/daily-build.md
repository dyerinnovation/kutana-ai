# Daily Build Sprint — Task Instructions

> These instructions are read and executed by the CoWork scheduled task.
> To change the build process, edit this file and push to main.

---

## Pre-flight

1. Pull the latest code:
   ```bash
   git pull origin main
   ```

2. Read the project conventions:
   ```
   Read CLAUDE.md at the repo root. Follow all conventions strictly.
   ```

3. Read the current state:
   ```
   Read docs/HANDOFF.md — check for warnings or items marked "DO NOT TOUCH"
   Read docs/PROGRESS.md — understand what was completed recently
   Read the last 10 git log --oneline entries to see recent changes
   ```

4. Check for infrastructure:
   ```bash
   docker compose ps
   ```
   If Postgres or Redis are not running, start them:
   ```bash
   docker compose up -d postgres redis
   ```

---

## Task Selection

1. Open `docs/TASKLIST.md`
2. Find the **first unchecked item** (`- [ ]`) that does NOT have a 🔒 lock icon
3. If all items in the current phase are complete, move to the next phase
4. If all items are complete or locked, write to HANDOFF.md: "All tasklist items complete or locked. Waiting for Jonathan to add new items or unlock." Then stop.

**Rules:**
- Pick exactly ONE item per session
- Never pick a locked item (🔒)
- Never skip ahead to a later phase if the current phase has unchecked items
- If an item has dependencies on incomplete items, skip it and pick the next eligible one

---

## Implementation

1. Create a feature branch:
   ```bash
   git checkout -b scheduled/$(date +%Y-%m-%d)-{feature-slug}
   ```
   Replace `{feature-slug}` with a short kebab-case description of the item (e.g., `assemblyai-stt-provider`, `pydantic-domain-models`).

2. Implement the roadmap item following CLAUDE.md conventions:
   - Python 3.12+ with strict type hints on every function
   - `async def` for all I/O operations
   - Pydantic v2 for data models with validators
   - SQLAlchemy 2.0 async style for ORM models
   - Google-style docstrings on all public methods
   - Structured logging with `logging` module

3. Write tests:
   - Create or update test files in the appropriate `tests/` directory
   - Use pytest with pytest-asyncio for async tests
   - Aim for at least one test per public method
   - Include both happy-path and error-case tests

4. Run quality checks:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy --strict .
   uv run pytest -x -v
   ```

5. Fix any issues found by the quality checks before proceeding.

---

## Post-implementation

1. Check off the completed item in `docs/TASKLIST.md`:
   ```markdown
   - [x] AssemblyAI streaming STT implementation   ← change [ ] to [x]
   ```

2. Append an entry to `docs/PROGRESS.md`:
   ```markdown
   ## YYYY-MM-DD — {Item Description}

   **Roadmap item:** {exact text from ROADMAP.md}
   **Branch:** scheduled/YYYY-MM-DD-{feature-slug}
   **Author:** CoWork (scheduled)

   ### Changes
   - Created `packages/convene-providers/src/convene_providers/stt/assemblyai_stt.py`
   - Created `packages/convene-providers/tests/test_assemblyai_stt.py`
   - Updated `packages/convene-providers/src/convene_providers/registry.py`

   ### Quality Check Results
   - ruff: ✅ No issues
   - mypy: ✅ No errors
   - pytest: ✅ 12 passed, 0 failed

   ### Notes
   {Any implementation decisions, trade-offs, or assumptions made}

   ### Blockers
   {List anything that needs Jonathan's input, or "None"}

   ### Next Up
   {The next unchecked item in ROADMAP.md}
   ```

3. Update `docs/HANDOFF.md` — replace the existing content with:
   ```markdown
   ## Latest Handoff

   **Author:** CoWork (scheduled)
   **Date:** {today's date and time}
   **What I did:** {1-2 sentence summary}
   **Branch:** scheduled/YYYY-MM-DD-{feature-slug}
   **Merge status:** Ready for review — do `git merge scheduled/YYYY-MM-DD-{slug}` after reviewing
   **Warnings:** {anything the next session (human or scheduled) should know}
   **Dependencies introduced:** {any new packages added to pyproject.toml}
   ```

4. Commit and push:
   ```bash
   git add .
   git commit -m "scheduled: {brief description of what was implemented}"
   git push origin scheduled/$(date +%Y-%m-%d)-{feature-slug}
   ```

---

## Hard rules

- **ONE item per session.** Never continue to the next roadmap item.
- **Never force-push.** Always create new commits.
- **Never modify files outside the scope of the current roadmap item** unless fixing an import or dependency required by your change.
- **Never delete or overwrite PROGRESS.md entries.** Always append.
- **If tests fail and you can't fix them in 3 attempts,** document the failure in PROGRESS.md, note it as a blocker in HANDOFF.md, and stop. Do not ship broken code.
- **If you encounter a merge conflict on pull,** stop and document it in HANDOFF.md. Do not attempt to resolve code merge conflicts — only resolve conflicts in docs/PROGRESS.md and docs/HANDOFF.md by keeping both versions.
