---
name: merge-worktree
description: Merge the current worktree branch into main and clean up. TRIGGER on: merge worktree, merge branch, finish feature, merge to main, complete work, clean up worktree.
permissions:
  - Bash(git:*)
---

# Merge Worktree

Merges the current worktree branch into main, then cleans up.

## Usage

```bash
bash .claude/skills/merge-worktree/scripts/merge-worktree.sh
```

## What it does

1. Stash any uncommitted changes
2. Fetch latest `main`
3. Check for merge conflicts (dry run)
4. If clean: merge into `main` and push
5. If conflicts: stop and list conflicting files for manual resolution
6. Remove the worktree branch after successful merge
7. Print confirmation

## Manual merge (if script flags conflicts)

```bash
git checkout main
git merge <branch-name>
# resolve conflicts
git add .
git commit
git push origin main
```
