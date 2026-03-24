#!/usr/bin/env bash
# Deploy Convene AI to the DGX Spark K3s cluster
set -euo pipefail

DGX=dgx
REPO_ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
SERVICE=${SERVICE:-}
SKIP_BUILD=${SKIP_BUILD:-}

echo "==> Syncing code to DGX..."
rsync -avz --exclude='.venv' --exclude='node_modules' --exclude='*.pyc' \
  --exclude='__pycache__' --exclude='.git' \
  "$REPO_ROOT/" "$DGX:~/convene-ai/"

if [[ -z "$SKIP_BUILD" ]]; then
  echo ""
  echo "==> Building Docker images on DGX..."
  if [[ -n "$SERVICE" ]]; then
    ssh "$DGX" "cd ~/convene-ai && docker build -t convene/$SERVICE -f services/$SERVICE/Dockerfile ."
    ssh "$DGX" "docker save convene/$SERVICE | echo JDf33nawm3! | sudo -S k3s ctr images import -"
  else
    ssh "$DGX" "cd ~/convene-ai && docker compose build"
    ssh "$DGX" "cd ~/convene-ai && for img in api-server agent-gateway audio-service task-engine mcp-server worker; do
      docker save convene/\$img 2>/dev/null | echo JDf33nawm3! | sudo -S k3s ctr images import - || true
    done"
  fi
fi

echo ""
echo "==> Applying Helm chart upgrades..."
CHART_FLAGS="--namespace convene --create-namespace"
if [[ -n "$SERVICE" ]]; then
  ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
    /home/jondyer3/.local/bin/helm upgrade --install convene-$SERVICE ~/convene-ai/charts/$SERVICE $CHART_FLAGS"
else
  ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
    /home/jondyer3/.local/bin/helm upgrade --install convene ~/convene-ai/charts/convene $CHART_FLAGS"
fi

echo ""
echo "==> Waiting for rollout..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
  kubectl -n convene wait --for=condition=ready pod --all --timeout=120s"

echo ""
echo "==> Health checks..."
curl -sk "https://convene.spark-b0f2.local/api/health" && echo "  API: OK" || echo "  API: FAIL"

echo ""
echo "==> Deploy complete."
