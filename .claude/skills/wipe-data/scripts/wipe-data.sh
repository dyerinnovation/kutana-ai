#!/usr/bin/env bash
# Wipe Convene AI data: drop/recreate DB, flush Redis
# DESTRUCTIVE — confirm before running
set -euo pipefail

DGX=dgx
MODE=${1:-}  # --redis-only | --db-only | --seed

if [[ "$MODE" != "--redis-only" && "$MODE" != "--db-only" ]]; then
  echo "WARNING: This will DROP the convene database and FLUSH all Redis data."
  read -p "Are you sure? (yes/no): " confirm
  [[ "$confirm" == "yes" ]] || { echo "Aborted."; exit 1; }
fi

# Helper: run kubectl exec on postgres pod
PG_CMD() {
  ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
    kubectl -n convene exec -i statefulset/postgres -- $*"
}

if [[ "$MODE" != "--redis-only" ]]; then
  echo "==> Dropping and recreating database..."
  PG_CMD psql -U convene -c "DROP DATABASE IF EXISTS convene;"
  PG_CMD psql -U convene -c "CREATE DATABASE convene;"
  echo "==> Running migrations..."
  ssh "$DGX" "cd ~/convene-ai && PATH=\$HOME/.local/bin:\$PATH uv run alembic upgrade head"
  echo "    Database reset."
fi

if [[ "$MODE" != "--db-only" ]]; then
  echo "==> Flushing Redis..."
  ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
    kubectl -n convene exec -i statefulset/redis -- redis-cli FLUSHALL"
  echo "    Redis flushed."
fi

if [[ "$MODE" == "--seed" ]]; then
  echo "==> Seeding test data..."
  ssh "$DGX" "cd ~/convene-ai && PATH=\$HOME/.local/bin:\$PATH uv run python scripts/seed_test_data.py"
  echo "    Seed complete."
fi

echo ""
echo "==> Wipe complete."
