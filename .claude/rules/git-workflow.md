# Git Workflow Rules

- **Remote is SSH**: `git@github.com:dyerinnovation/convene-ai.git`. Never use HTTPS (GCM hangs in non-interactive shells).
- **Co-author trailer**: every commit message must end with `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`.
- **Commit cadence**: commit and push after each plan. Keep commits small — large commits with many files can hang on push.
- **TASKLIST lock**: add 🔒 to a TASKLIST item when starting work. Replace `- [ ] 🔒` with `- [x]` when done. Only the session that locked it should unlock it.
- **Milestone items (🏁)** are verification checkpoints, not implementation tasks — check them off only when prerequisites pass.
- See `claude_docs/Git_Best_Practices.md` for full details.

## Worktree Merge Protocol
- Code tasks run in isolated worktrees. Before completing ANY task, merge your worktree branch to main and push.
- Never leave code stranded in a worktree. If you wrote code, it must be on main before you report done.
- Merge steps: stash any WIP on main, checkout main, merge the worktree branch, push, clean up worktree.
- If merge conflicts occur, resolve them. If you can't resolve, report the conflict — don't silently leave code unmerged.
- Use the `/merge-worktree` skill for the full procedure.
