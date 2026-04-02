#!/usr/bin/env bash
# Wipe Kutana AI data: drop/recreate DB, flush Redis
# DESTRUCTIVE — confirm before running
set -euo pipefail

DGX=dgx
MODE=${1:-}  # --redis-only | --db-only | --seed

if [[ "$MODE" != "--redis-only" && "$MODE" != "--db-only" ]]; then
  echo "WARNING: This will DROP the kutana database and FLUSH all Redis data."
  read -p "Are you sure? (yes/no): " confirm
  [[ "$confirm" == "yes" ]] || { echo "Aborted."; exit 1; }
fi

# Helper: run kubectl exec on postgres pod
PG_CMD() {
  kubectl -n kutana exec -i statefulset/postgres -- "$@"
}

if [[ "$MODE" != "--redis-only" ]]; then
  echo "==> Dropping and recreating database..."
  PG_CMD psql -U kutana -c "DROP DATABASE IF EXISTS kutana;"
  PG_CMD psql -U kutana -c "CREATE DATABASE kutana;"
  echo "==> Running migrations..."
  ssh "$DGX" "cd ~/kutana-ai && PATH=\$HOME/.local/bin:\$PATH uv run alembic upgrade head"
  echo "    Database reset."
fi

if [[ "$MODE" != "--db-only" ]]; then
  echo "==> Flushing Redis..."
  kubectl -n kutana exec -i statefulset/redis -- redis-cli FLUSHALL
  echo "    Redis flushed."
fi

if [[ "$MODE" == "--seed" ]]; then
  echo "==> Seeding test data..."
  ssh "$DGX" "cd ~/kutana-ai && PATH=\$HOME/.local/bin:\$PATH uv run python scripts/seed_test_data.py"
  echo "    Seed complete."
fi

echo ""
echo "==> Wipe complete."
