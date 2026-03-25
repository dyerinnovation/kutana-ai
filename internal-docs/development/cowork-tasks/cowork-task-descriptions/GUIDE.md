# Task Description Files — Guide

## What are task description files?

The `.md` files in this directory contain the full instructions for each CoWork scheduled task. They define exactly what the task does: which files to read, what commands to run, what output to produce, and what rules to follow.

## How CoWork reads them

Each CoWork scheduled task is configured in the Claude Desktop UI with a minimal "thin prompt" that simply points to one of these files:

```
Follow the instructions in docs/cowork-tasks/cowork-task-descriptions/daily-build.md exactly.
Read CLAUDE.md first for project conventions.
```

The CoWork UI controls **when** and **whether** a task runs. These files control **what** it does. This separation means you can iterate on task behavior through normal git workflows (edit, commit, push) without touching the CoWork UI.

## How to modify an existing task

1. Edit the relevant `.md` file in this directory
2. Commit and push to `main`:
   ```bash
   git add docs/cowork-tasks/cowork-task-descriptions/<file>.md
   git commit -m "Update <task-name>: <what changed>"
   git push origin main
   ```
3. The next scheduled run will automatically pick up the updated instructions

### Example: changing output paths

When this directory was reorganized, the output paths in `daily-review.md` and `weekly-architecture-review.md` were updated from:

```
docs/cowork-task-output/DAILY_BRIEF.md
```

to:

```
docs/cowork-tasks/cowork-task-output/DAILY_BRIEF.md
```

This is a one-line change in each file, committed and pushed — the next scheduled run writes to the new location.

## How to add a new task

1. Create a new `.md` file in this directory with the task instructions
   - Follow the structure of existing files: a header block, a process section, an output section, and hard rules
2. In the CoWork Scheduled sidebar in Claude Desktop, create a new task:
   - Set the name, schedule, and model
   - Set the prompt to point to your new file:
     ```
     Follow the instructions in docs/cowork-tasks/cowork-task-descriptions/<your-file>.md exactly.
     Read CLAUDE.md first for project conventions.
     ```
3. Update `docs/cowork-tasks/README.md` — add a row to the "Active tasks" table

## Current task files

| File | Task | Schedule |
|------|------|----------|
| `daily-build.md` | Daily Build Sprint | Weekdays 7:00 AM |
| `daily-review.md` | Daily Review Brief | Weekdays 8:30 AM |
| `weekly-architecture-review.md` | Weekly Architecture Review | Fridays 4:00 PM |
