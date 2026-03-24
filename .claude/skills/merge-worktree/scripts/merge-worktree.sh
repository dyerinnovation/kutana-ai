#!/usr/bin/env bash
# Merge the current worktree branch into main and clean up
set -euo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)
REMOTE="origin"

if [[ "$BRANCH" == "main" ]]; then
  echo "Already on main. Nothing to merge."
  exit 0
fi

echo "==> Current branch: $BRANCH"
echo "==> Target: main"
echo ""

# Stash uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "==> Stashing uncommitted changes..."
  git stash push -m "merge-worktree auto-stash"
fi

# Fetch latest main
echo "==> Fetching latest main..."
git fetch "$REMOTE" main

# Check for conflicts (dry run via merge-tree)
echo "==> Checking for merge conflicts..."
BASE=$(git merge-base "$BRANCH" "$REMOTE/main")
CONFLICTS=$(git merge-tree "$BASE" "$BRANCH" "$REMOTE/main" 2>&1 | grep -c "^CONFLICT" || true)

if [[ "$CONFLICTS" -gt 0 ]]; then
  echo ""
  echo "CONFLICTS DETECTED ($CONFLICTS files). Resolve manually:"
  git merge-tree "$BASE" "$BRANCH" "$REMOTE/main" | grep "^CONFLICT"
  echo ""
  echo "Manual steps:"
  echo "  git checkout main"
  echo "  git merge $BRANCH"
  echo "  # resolve conflicts"
  echo "  git push origin main"
  exit 1
fi

echo "==> No conflicts. Merging into main..."
git checkout main
git merge --no-ff "$BRANCH" -m "Merge branch '$BRANCH'"
git push "$REMOTE" main

echo ""
echo "==> Cleaning up branch $BRANCH..."
git branch -d "$BRANCH"
git push "$REMOTE" --delete "$BRANCH" 2>/dev/null || true

echo ""
echo "==> Merge complete. On main."
