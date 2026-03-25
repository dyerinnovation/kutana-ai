#!/usr/bin/env bash
# Deploy Convene AI to the DGX Spark K3s cluster
set -euo pipefail

DGX=dgx
SERVICE=${1:-}
SKIP_BUILD=${SKIP_BUILD:-}

# 1. Sync code via git (not rsync)
echo "==> Pushing code to GitHub..."
git push

echo "==> Pulling latest on DGX..."
ssh "$DGX" 'cd ~/convene-ai && git pull'

# 2. Build & push images (unless SKIP_BUILD is set)
if [[ -z "$SKIP_BUILD" ]]; then
  echo ""
  echo "==> Building Docker images on DGX..."
  if [[ -n "$SERVICE" ]]; then
    ssh "$DGX" "cd ~/convene-ai && bash scripts/build_and_push.sh $SERVICE"
  else
    ssh "$DGX" 'cd ~/convene-ai && bash scripts/build_and_push.sh all'
  fi
fi

# 3. Helm upgrade
echo ""
echo "==> Applying Helm chart..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
  /home/jondyer3/.local/bin/helm upgrade --install convene ~/convene-ai/charts/convene -n convene --create-namespace"

# 4. Wait for rollout
echo ""
echo "==> Waiting for pods..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
  kubectl -n convene wait --for=condition=ready pod --all --timeout=120s"

# 5. Status + health check
echo ""
echo "==> Pod status:"
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
  kubectl -n convene get pods"

echo ""
curl -sk "https://convene.spark-b0f2.local/api/health" && echo "  API: OK" || echo "  API: FAIL"
curl -sk -o /dev/null -w "  Frontend: %{http_code}\n" "https://convene.spark-b0f2.local/"

echo ""
echo "==> Deploy complete."
