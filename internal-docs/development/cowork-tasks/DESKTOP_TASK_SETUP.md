# Desktop Scheduled Tasks — Setup Guide

> This guide walks you through creating the local desktop scheduled tasks in the
> Claude Code Desktop app. These run on your Mac mini with full local file access.
>
> For cloud versions (post-launch on GCP), see `cowork-task-descriptions/`.
> For local versions, see `local-task-descriptions/`.

---

## Prerequisites

- Claude Code Desktop app open
- Mac mini awake and connected to network
- External SSD mounted at `/Volumes/Dev_SSD/`
- SSH access to DGX configured (host alias `dgx` in `~/.ssh/config`)

---

## Task 1: Morning Status Sync

**Create in Claude Code Desktop → Scheduled → New local task**

| Field | Value |
|---|---|
| Name | `kutana-morning-status` |
| Description | Daily status: git activity, tasklist, DGX health → Obsidian vault |
| Frequency | Weekdays |
| Time | 7:00 AM |
| Model | Haiku |
| Working Folder | `~/Documents/dev/kutana-ai` |

**Prompt (copy/paste this exactly):**

```
git pull origin main
Follow the instructions in internal-docs/development/cowork-tasks/local-task-descriptions/morning-status-local.md exactly.
Read CLAUDE.md first for project conventions.
```

---

## Task 2: Infrastructure Health Check

| Field | Value |
|---|---|
| Name | `kutana-infra-health` |
| Description | DGX/K3s health monitoring, silent when healthy |
| Frequency | Custom: `0 */6 * * *` (every 6 hours) |
| Time | N/A (cron handles it) |
| Model | Haiku |
| Working Folder | `~/Documents/dev/kutana-ai` |

**Prompt:**

```
git pull origin main
Follow the instructions in internal-docs/development/cowork-tasks/local-task-descriptions/infra-health-check-local.md exactly.
Read CLAUDE.md first for project conventions.
```

---

## Task 3: Weekly Architecture Review

| Field | Value |
|---|---|
| Name | `kutana-weekly-architecture` |
| Description | Deep codebase analysis, tech debt tracking → Obsidian vault |
| Frequency | Weekly (Friday) |
| Time | 4:00 PM |
| Model | Opus |
| Working Folder | `~/Documents/dev/kutana-ai` |

**Prompt:**

```
git pull origin main
Follow the instructions in internal-docs/development/cowork-tasks/local-task-descriptions/weekly-architecture-review-local.md exactly.
Read CLAUDE.md first for project conventions.
```

---

## After Creating Each Task

1. Click **Run now** to trigger a test run
2. Approve any tool permission prompts that appear (these get saved for future runs)
3. Verify the output was written to the Obsidian vault

---

## Changing Task Behavior

Edit the corresponding `.md` file in `local-task-descriptions/`, commit, and push to main.
The next scheduled run will pick up the changes automatically.
