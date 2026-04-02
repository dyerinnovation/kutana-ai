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
2. Find the **first unchecked item** (`- [ ]`) or **block** (`🔗 BLOCK:`) that does NOT have a 🔒 lock icon
3. If the selected item is a `🔗 BLOCK:`, enter **block mode** (see below)
4. If all items in the current phase are complete, move to the next phase
5. If all items are complete or locked, write to HANDOFF.md: "All tasklist items complete or locked. Waiting for Jonathan to add new items or unlock." Then stop.

**Rules:**
- Pick exactly **ONE BLOCK or ONE item** per session
- Never pick a locked item (🔒)
- Never skip ahead to a later phase if the current phase has unchecked items
- If an item has dependencies on incomplete items, skip it and pick the next eligible one

### Block Mode

When the selected item is a `🔗 BLOCK:`, work through all sub-tasks as a unit:

1. Implement the first sub-task following the Implementation steps below
2. Run quality checks after each sub-task
3. If a sub-task passes, check it off and move to the next
4. If a sub-task fails after 3 fix attempts, document the failure and stop — **partial block completion is OK**
5. Check off the entire `🔗 BLOCK:` line only when ALL sub-tasks pass
6. If a block has >5 sub-tasks and quality checks pass on the first N, commit progress and continue to the next sub-task

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
   For blocks, check off each sub-task AND the block header when all sub-tasks pass.

2. Append an entry to `docs/PROGRESS.md`.

   **For single items:**
   ```markdown
   ## YYYY-MM-DD — {Item Description}

   **Roadmap item:** {exact text from TASKLIST.md}
   **Branch:** scheduled/YYYY-MM-DD-{feature-slug}
   **Author:** CoWork (scheduled)

   ### Changes
   - Created `packages/kutana-providers/src/kutana_providers/stt/assemblyai_stt.py`
   - Created `packages/kutana-providers/tests/test_assemblyai_stt.py`
   - Updated `packages/kutana-providers/src/kutana_providers/registry.py`

   ### Quality Check Results
   - ruff: ✅ No issues
   - mypy: ✅ No errors
   - pytest: ✅ 12 passed, 0 failed

   ### Notes
   {Any implementation decisions, trade-offs, or assumptions made}

   ### Blockers
   {List anything that needs Jonathan's input, or "None"}

   ### Next Up
   {The next unchecked item in TASKLIST.md}
   ```

   **For blocks:**
   ```markdown
   ## YYYY-MM-DD — BLOCK: {Block Title}

   **Block status:** N/M sub-tasks complete
   **Branch:** scheduled/YYYY-MM-DD-{feature-slug}
   **Author:** CoWork (scheduled)

   ### Sub-task 1: {Name}
   **Status:** ✅
   - Created `path/to/file.py`
   - Quality: ruff ✅, mypy ✅, pytest ✅ (N passed)

   ### Sub-task 2: {Name}
   **Status:** ✅
   - Created `path/to/file.py`
   - Quality: ruff ✅, mypy ✅, pytest ✅ (N passed)

   ### Sub-task 3: {Name}
   **Status:** ❌ (failed after 3 attempts)
   - Issue: {description of failure}
   - Attempted fixes: {what was tried}

   ### Notes
   {Any implementation decisions, trade-offs, or assumptions made}

   ### Blockers
   {List anything that needs Jonathan's input, or "None"}

   ### Next Up
   {The next unchecked item/block in TASKLIST.md}
   ```

3. Update `docs/HANDOFF.md` — replace the existing content with:
   ```markdown
   ## Latest Handoff

   **Author:** CoWork (scheduled)
   **Date:** {today's date and time}
   **What I did:** {1-2 sentence summary}
   **Branch:** scheduled/YYYY-MM-DD-{feature-slug}
   **Block progress:** {if block: "3 of 4 sub-tasks complete", else omit}
   **Merge status:** {✅ Merged to main | ❌ Merge FAILED — branch left unmerged for manual review}
   **Warnings:** {anything the next session (human or scheduled) should know}
   **Dependencies introduced:** {any new packages added to pyproject.toml}
   ```

4. Commit and push:
   ```bash
   git add .
   git commit -m "scheduled: {brief description of what was implemented}"
   git push origin scheduled/$(date +%Y-%m-%d)-{feature-slug}
   ```

5. Merge to main:
   ```bash
   git checkout main
   git pull origin main
   git merge --no-ff scheduled/$(date +%Y-%m-%d)-{feature-slug} -m "merge: scheduled/$(date +%Y-%m-%d)-{feature-slug} into main"
   git push origin main
   ```

   **If the merge succeeds:** Update the `**Merge status:**` line in `docs/HANDOFF.md` to `✅ Merged to main`.

   **If the merge fails** (conflict or any error):
   - Do **not** force the merge — abort with `git merge --abort` and return to the feature branch
   - Append a note to the bottom of the `docs/PROGRESS.md` entry for today:
     ```markdown
     **Merge status:** ❌ FAILED — conflict or error. Branch left unmerged for manual review.
     ```
   - Update the `**Merge status:**` line in `docs/HANDOFF.md` to `❌ Merge FAILED — branch left unmerged for manual review`
   - Push the feature branch as-is and stop — do not push main

---

## Hard rules

- **ONE BLOCK or ONE item per session.** A block is complete when all sub-tasks pass quality checks. Never continue to the next block/item after completing one.
- **Never force-push.** Always create new commits.
- **Never modify files outside the scope of the current roadmap item** unless fixing an import or dependency required by your change.
- **Never delete or overwrite PROGRESS.md entries.** Always append.
- **If tests fail and you can't fix them in 3 attempts,** document the failure in PROGRESS.md, note it as a blocker in HANDOFF.md, and stop. Do not ship broken code.
- **If you encounter a merge conflict on pull,** stop and document it in HANDOFF.md. Do not attempt to resolve code merge conflicts — only resolve conflicts in docs/PROGRESS.md and docs/HANDOFF.md by keeping both versions.
- **Never force a merge to main.** If `git merge --no-ff` fails for any reason, abort immediately with `git merge --abort`, document the failure, and leave the branch unmerged for manual review.
- **Partial block completion is OK.** If 2 of 4 sub-tasks pass but the 3rd fails, commit the passing work, document the failure, and stop. Check off the completed sub-tasks but NOT the block header.
