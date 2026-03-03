# Git Best Practices — Convene AI

## Commit and Push Cadence
- **Push after each plan completes** — never let uncommitted changes accumulate across sessions
- If a session ends without pushing, the next session inherits a large diff that's hard to push

## Commit Size
- Keep commits small and focused (one logical change per commit)
- Large commits (100+ files, 10K+ lines) can hang on push — batch into logical chunks
- Group by area: core models, providers, services, docs, infra/charts

## SSH Setup
- GitHub remote uses SSH: `git@github.com:dyerinnovation/convene-ai.git`
- SSH key: `~/.ssh/dyerinnovation-key`
- Config in `~/.ssh/config` maps `github.com` to this key
- HTTPS with Git Credential Manager (GCM) hangs in non-interactive shells — always use SSH

## Branch Strategy
- Feature branches: `feat/<description>` or `scheduled/<date>-<description>`
- Push with `--set-upstream` on first push of a new branch
- Create PRs via `gh pr create`

## Commit Messages
- Format: `type: short description` (e.g., `fix:`, `feat:`, `docs:`, `refactor:`)
- Body for details when needed
- Always include co-author trailer: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
