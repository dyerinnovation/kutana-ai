# Morning Status Sync — Task Instructions

> These instructions are read and executed by the CoWork scheduled task.
> To change the process, edit this file and push to main.

---

## Purpose

Generate a daily status report covering git activity, tasklist state, and infrastructure health. Write results to the Obsidian vault so both Dispatch and Code sessions can reference them.

---

## Process

1. Read project conventions:
   ```
   Read CLAUDE.md at the repo root. Follow all conventions strictly.
   ```

2. Read current state:
   ```
   Read internal-docs/development/HANDOFF.md — check for warnings
   Read internal-docs/development/TASKLIST.md — identify next 3 unchecked items
   ```

3. Git activity (last 24h):
   ```bash
   git log --oneline --since='24 hours ago'
   git diff --stat HEAD~5..HEAD 2>/dev/null || echo "Less than 5 commits"
   ```

4. DGX health check:
   ```bash
   ssh dgx 'kubectl get pods -n kutana && kubectl get nodes && df -h / && free -h && uptime' 2>&1 || echo "SSH to DGX failed — check connectivity"
   ```

5. Write status to Obsidian vault:

   Create/overwrite `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Status/current-sprint.md`:

   ```markdown
   ---
   updated: {YYYY-MM-DD}
   type: status
   ---

   # Current Sprint Status — {YYYY-MM-DD}

   ## Git Activity (Last 24h)
   {commits or 'No commits in last 24h'}

   ## Next Up (from TASKLIST.md)
   {next 3 unchecked items with their phase/block context}

   ## Handoff Warnings
   {warnings from HANDOFF.md or 'None'}

   ## Infrastructure
   {DGX health results — pods, nodes, disk, memory, uptime}
   ```

6. Write daily report to Obsidian vault:

   Create `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Reports/daily/{YYYY-MM-DD}.md` with the same content as current-sprint.md.

---

## Hard rules

- **Never modify code files.** This task is read-only analysis + Obsidian vault writes.
- **Be concise.** The goal is a 2-minute morning read.
- **Always write the report.** Even if nothing changed, write the report confirming it.
- **If the Obsidian vault is not mounted** (external SSD disconnected), write the report to `internal-docs/development/cowork-tasks/cowork-task-output/DAILY_BRIEF.md` as a fallback.
