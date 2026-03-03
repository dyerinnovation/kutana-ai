# Fix Git Commit Attribution (jcdpath → dyerinnovation)

## Problem
Commits pushed to `dyerinnovation/convene-ai` show as authored by `jcdpath` on GitHub because:
- Global git config sets `user.email=jonathan@yourpath.ai`
- That email is registered to the `jcdpath` GitHub account
- GitHub maps commit author emails to accounts

## Steps
1. Set repo-local git user config (`user.email` and `user.name`) for convene-ai
2. Rewrite all existing commits with `git rebase --root` to update author/committer
3. Force push with `--force-with-lease`
4. Verify attribution via `gh api`

## Expected Outcome
- All 24 commits attributed to `dyerinnovation` on GitHub
- Future commits automatically use the correct identity
