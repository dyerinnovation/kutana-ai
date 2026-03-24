# Git Workflow Rules

- **Remote is SSH**: `git@github.com:dyerinnovation/convene-ai.git`. Never use HTTPS (GCM hangs in non-interactive shells).
- **Co-author trailer**: every commit message must end with `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`.
- **Commit cadence**: commit and push after each plan. Keep commits small — large commits with many files can hang on push.
- **TASKLIST lock**: add 🔒 to a TASKLIST item when starting work. Replace `- [ ] 🔒` with `- [x]` when done. Only the session that locked it should unlock it.
- **Milestone items (🏁)** are verification checkpoints, not implementation tasks — check them off only when prerequisites pass.
- See `claude_docs/Git_Best_Practices.md` for full details.
