# Morning Status Sync — Local Desktop Task

> Local version of the morning status task. Runs as a Claude Code Desktop scheduled task
> with full local filesystem and SSH access.
>
> Working folder is `~/Documents/dev/kutana-ai-dev`. Iterate through all repos in that
> directory (kutana-ai, kutana-android, kutana-ios) — pull and check git activity for each.

---

## Purpose

Same as the cloud version — generate daily status report. The local version has direct access
to the filesystem, SSH, and the Obsidian vault on the external SSD.

---

## Process

1. Pull latest from all repos:
   ```bash
   for repo in kutana-ai kutana-android kutana-ios; do
     echo "=== $repo ===" && cd ~/Documents/dev/kutana-ai-dev/$repo && git pull origin main
   done
   ```

2. Read current state (from kutana-ai):
   - Read `kutana-ai/CLAUDE.md` for conventions
   - Read `kutana-ai/internal-docs/development/HANDOFF.md` for warnings
   - Read `kutana-ai/internal-docs/development/TASKLIST.md` — identify next 3 unchecked items

3. Git activity (last 24h) — check all repos:
   ```bash
   for repo in kutana-ai kutana-android kutana-ios; do
     echo "=== $repo ===" && cd ~/Documents/dev/kutana-ai-dev/$repo
     git log --oneline --since='24 hours ago'
     git diff --stat HEAD~5..HEAD 2>/dev/null || echo "Less than 5 commits"
   done
   ```

4. DGX health check:
   ```bash
   ssh dgx 'kubectl get pods -n kutana && kubectl get nodes && df -h / && free -h && uptime'
   ```

5. Write to Obsidian vault at `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Status/current-sprint.md`:

   ```markdown
   ---
   updated: {YYYY-MM-DD}
   type: status
   ---

   # Current Sprint Status — {YYYY-MM-DD}

   ## Git Activity (Last 24h)
   {commits or 'No commits in last 24h'}

   ## Next Up (from TASKLIST.md)
   {next 3 unchecked items}

   ## Handoff Warnings
   {warnings from HANDOFF.md or 'None'}

   ## Infrastructure
   {DGX health — pods, nodes, disk, memory, uptime}
   ```

6. Also write to `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Reports/daily/{YYYY-MM-DD}.md`

---

## Hard rules

- Never modify code files. Read-only analysis + vault writes only.
- Be concise. 2-minute morning read.
- Always write the report even if nothing changed.
