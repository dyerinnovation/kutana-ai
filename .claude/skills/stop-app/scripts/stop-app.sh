#!/usr/bin/env bash
# Stop Convene AI services on the DGX Spark K3s cluster
set -euo pipefail

NAMESPACE=convene
DGX=dgx
FULL=${1:-}

echo "==> Scaling down Convene service deployments..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE scale deployment --all --replicas=0"

echo ""
echo "==> Waiting for pods to terminate..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE wait --for=delete pod --all --timeout=60s" || true

if [[ "$FULL" == "--full" ]]; then
  echo ""
  echo "==> --full flag set: also stopping infrastructure (postgres, redis)..."
  ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE scale statefulset --all --replicas=0"
  echo "    Infrastructure stopped."
fi

echo ""
echo "==> Final pod status:"
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE get pods"
echo ""
echo "==> Services stopped."
