# Convene AI — CoWork Scheduled Tasks Setup Guide

> This guide walks you through setting up automated daily development sprints for Convene AI using Claude CoWork's scheduled tasks feature. The pattern enables incremental, token-efficient development where CoWork builds one feature per day and you review the work each morning.

---

## Prerequisites

- [ ] Claude Desktop app installed and open
- [ ] Claude Max subscription (CoWork requires this)
- [ ] Convene AI repo cloned locally (e.g., `~/projects/convene-ai/`)
- [ ] Git configured with SSH or HTTPS push access to your remote
- [ ] Docker Desktop running (for Postgres + Redis)
- [ ] `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

---

## Step 1: Add the coordination files to your repo

Copy the following files from this package into your Convene AI repo:

```
convene-ai/
├── docs/
│   ├── TASKLIST.md                          # Ordered task checklist (your task queue)
│   ├── PROGRESS.md                         # Running log of completed work
│   ├── HANDOFF.md                          # Shift-change notes between you and CoWork
│   ├── technical/
│   │   ├── BOOTSTRAP_REFERENCE.md          # Bootstrap reference documentation
│   │   ├── COMPETITIVE_ANALYSIS.md         # Competitive analysis
│   │   ├── GO_TO_MARKET.md                 # Go-to-market strategy
│   │   ├── ROADMAP.md                      # Product roadmap
│   │   └── VISION.md                       # Product vision
│   └── cowork-tasks/
│       ├── README.md                       # Explains the scheduling pattern
│       ├── cowork-task-output/
│       │   ├── WEEKLY_REVIEW.md            # Architecture review output (auto-generated)
│       │   └── DAILY_BRIEF.md              # Morning briefing output (auto-generated)
│       └── cowork-task-descriptions/
│           ├── GUIDE.md                    # How to modify task descriptions
│           ├── daily-build.md              # Instructions for the daily build sprint
│           ├── daily-review.md             # Instructions for the daily review brief
│           └── weekly-architecture-review.md # Instructions for the Friday review
```

After copying, commit and push:

```bash
cd ~/projects/convene-ai
git add docs/
git commit -m "Add CoWork scheduled task coordination files"
git push origin main
```

---

## Step 2: Create the Daily Build Sprint task in CoWork

1. Open the Claude Desktop app
2. Click **"Scheduled"** in the left sidebar
3. Click **"New Scheduled Task"** (or the + button)
4. Fill in the fields:

| Field | Value |
|---|---|
| **Name** | `Convene AI — Daily Build Sprint` |
| **Description** | `Implements the next uncompleted roadmap item for Convene AI. One feature per session.` |
| **Frequency** | `Weekdays` |
| **Time** | `7:00 AM` (or whenever you want work done before you wake up) |
| **Model** | `Claude Sonnet` (good balance of speed/cost for code generation — use Opus for complex architecture work) |
| **Working Folder** | `~/projects/convene-ai` |

5. In the **Prompt Instructions** field, paste this exact text:

```
Follow the instructions in docs/cowork-tasks/cowork-task-descriptions/daily-build.md exactly.
Do not deviate from the process described in that file.
Read CLAUDE.md first for project conventions.
```

6. Save the task

> **Why keep the prompt thin?** The detailed instructions live in `daily-build.md` inside your repo. This means you can version control, branch, and iterate on the build process without ever touching the CoWork UI. The CoWork prompt is just a pointer.

---

## Step 3: Create the Daily Review Brief task in CoWork

1. Still in the Scheduled sidebar, create another task:

| Field | Value |
|---|---|
| **Name** | `Convene AI — Daily Review Brief` |
| **Description** | `Generates a morning briefing summarizing the daily build sprint results.` |
| **Frequency** | `Weekdays` |
| **Time** | `8:30 AM` (90 minutes after the build sprint) |
| **Model** | `Claude Haiku` (this is a lightweight summarization task) |
| **Working Folder** | `~/projects/convene-ai` |

2. Prompt Instructions:

```
Follow the instructions in docs/cowork-tasks/cowork-task-descriptions/daily-review.md exactly.
Read CLAUDE.md first for project conventions.
```

---

## Step 4: Create the Weekly Architecture Review task in CoWork

1. Create a third task:

| Field | Value |
|---|---|
| **Name** | `Convene AI — Weekly Architecture Review` |
| **Description** | `Reviews full codebase against design principles. Identifies drift, gaps, and refactoring priorities.` |
| **Frequency** | `Weekly (Fridays)` |
| **Time** | `4:00 PM` |
| **Model** | `Claude Opus` (deep analysis benefits from the strongest model) |
| **Working Folder** | `~/projects/convene-ai` |

2. Prompt Instructions:

```
Follow the instructions in docs/cowork-tasks/cowork-task-descriptions/weekly-architecture-review.md exactly.
Read CLAUDE.md first for project conventions.
```

---

## Step 5: Understand the daily workflow

Here's what a typical day looks like once everything is running:

### The night before (you)
1. Finish your Claude Code session working on Convene AI
2. Update `docs/HANDOFF.md` with what you did and any warnings for the next session
3. If you worked on something in TASKLIST.md, check it off
4. Commit and push to `main`
5. Close your laptop (or leave it open with Claude Desktop running)

### 7:00 AM (CoWork — Daily Build Sprint)
1. Pulls latest `main`
2. Reads HANDOFF.md, PROGRESS.md, and TASKLIST.md
3. Creates a new branch: `scheduled/YYYY-MM-DD-{feature-slug}`
4. Picks the next unchecked, unlocked item from TASKLIST.md
5. Implements it (code, tests, type checking)
6. Updates PROGRESS.md with what was done
7. Updates HANDOFF.md with notes for you
8. Commits and pushes the feature branch
9. Stops — does NOT continue to the next item

### 8:30 AM (CoWork — Daily Review Brief)
1. Reads PROGRESS.md and the latest branch diff
2. Writes a concise briefing to `docs/cowork-tasks/cowork-task-output/DAILY_BRIEF.md`
3. Flags any blockers, test failures, or decisions needed

### 9:00 AM (you — morning review)
1. Open your laptop, grab coffee
2. Read `docs/cowork-tasks/cowork-task-output/DAILY_BRIEF.md` — this is your 2-minute summary
3. If the work looks good:
   ```bash
   git checkout main
   git pull
   git merge scheduled/2026-02-27-assemblyai-stt
   git push origin main
   git branch -d scheduled/2026-02-27-assemblyai-stt
   ```
4. If something needs fixing, open a Claude Code session on the branch and iterate
5. Optionally update TASKLIST.md to reorder priorities or add items
6. Commit and push — you're set for tomorrow's sprint

### Friday 4:00 PM (CoWork — Weekly Architecture Review)
1. Reviews entire codebase against CLAUDE.md design principles
2. Checks test coverage, type safety, provider abstraction consistency
3. Writes `docs/cowork-tasks/cowork-task-output/WEEKLY_REVIEW.md` with findings and priorities for next week
4. You read it over the weekend or Monday morning and adjust TASKLIST.md accordingly

---

## Step 6: Coordination patterns to avoid conflicts

### Lock items you're actively working on

In `TASKLIST.md`, mark items you're touching so the scheduled task skips them:

```markdown
- [ ] 🔒 AudioPipeline transcoding (IN PROGRESS — Jonathan)
- [ ] Redis Streams publishing         ← CoWork will pick this one instead
```

The daily build task is instructed to skip any item with 🔒.

### Use feature branches to prevent merge conflicts

The scheduled task always works on a dedicated branch (`scheduled/YYYY-MM-DD-*`). You work on `main` or your own feature branches. This means you never collide. You merge the scheduled branch when you're ready.

### The HANDOFF.md protocol

Think of this as shift change notes. Both you and CoWork write to it:

```markdown
## Latest Handoff

**Author:** Jonathan
**Date:** 2026-02-26 11:30 PM
**What I did:** Built TwilioHandler websocket endpoint, tests passing.
AudioPipeline is scaffolded but transcoding logic is incomplete — DO NOT
implement yet, I have a specific approach I want to try tomorrow.
**Warnings:** The twilio_handler.py imports are temporary — I'm going to
refactor the audio format constants into convene-core tomorrow.
```

---

## Step 7: Changing task behavior over time

### Modifying what the daily build does

Since the real instructions live in `docs/cowork-tasks/cowork-task-descriptions/daily-build.md`, just edit that file:

```bash
# Edit the instructions
vim docs/cowork-tasks/cowork-task-descriptions/daily-build.md

# Commit the change
git add docs/cowork-tasks/cowork-task-descriptions/daily-build.md
git commit -m "Update daily build: add integration test step"
git push origin main
```

The next morning's scheduled run will automatically use the updated instructions.

### Experimenting with a different approach

```bash
git checkout -b experiment/new-build-strategy
# Edit docs/cowork-tasks/cowork-task-descriptions/daily-build.md with experimental instructions
git commit -am "Experiment: have daily build focus on test coverage"
git push origin experiment/new-build-strategy
```

Note: The scheduled task will still pull `main` by default. To test experimental instructions, you'd temporarily update the CoWork task's working folder to point at the experiment branch, or update the prompt to `git checkout experiment/new-build-strategy` before reading instructions.

### Pausing or adjusting schedule

In the CoWork Scheduled sidebar, you can disable/enable individual tasks, change frequency, or adjust times without touching your repo files. The repo files control *what* gets done; the CoWork UI controls *when* and *whether* it runs.

---

## Troubleshooting

### Scheduled task didn't run
Your laptop was probably asleep or Claude Desktop was closed. CoWork will run missed tasks when you open the app. Check the Scheduled sidebar for execution status.

### Merge conflicts on PROGRESS.md or HANDOFF.md
These are append-only files, so conflicts should be rare. If they happen, the scheduled task is instructed to resolve by keeping both versions. Worst case, you resolve manually — these are just coordination docs, not code.

### Task is implementing the wrong thing
Check `TASKLIST.md` — is the ordering correct? Is the item you expected it to pick actually the next unchecked, unlocked item? Update the roadmap and push.

### Token usage seems high
Check if the daily build task is trying to do too much. The one-item-per-session constraint is enforced in `daily-build.md`. If a single item is too large (e.g., "Implement entire audio service"), break it into smaller sub-items in TASKLIST.md.

---

## File Reference

| File | Purpose | Who writes it |
|---|---|---|
| `CLAUDE.md` | Project conventions and architecture | You (initial setup) |
| `docs/TASKLIST.md` | Ordered task queue | You (CoWork checks items off) |
| `docs/PROGRESS.md` | Running development log | CoWork (you review) |
| `docs/HANDOFF.md` | Shift change notes | Both |
| `docs/cowork-tasks/cowork-task-output/DAILY_BRIEF.md` | Morning summary | CoWork (daily review task) |
| `docs/cowork-tasks/cowork-task-output/WEEKLY_REVIEW.md` | Architecture assessment | CoWork (weekly review task) |
| `docs/cowork-tasks/cowork-task-descriptions/*.md` | Task instructions (version controlled) | You |
