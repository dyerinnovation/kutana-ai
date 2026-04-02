#!/usr/bin/env bash
# Stop Kutana AI services on the DGX Spark K3s cluster
set -euo pipefail

NAMESPACE=kutana
FULL=${1:-}

DEPLOYMENTS="api-server agent-gateway audio-service task-engine mcp-server web"
echo "==> Scaling down Kutana service deployments..."
kubectl -n $NAMESPACE scale deployment $DEPLOYMENTS --replicas=0

echo ""
echo "==> Waiting for pods to terminate..."
kubectl -n $NAMESPACE wait --for=delete pod --all --timeout=60s || true

if [[ "$FULL" == "--full" ]]; then
  echo ""
  echo "==> --full flag set: also stopping infrastructure (postgres, redis)..."
  kubectl -n $NAMESPACE scale statefulset --all --replicas=0
  echo "    Infrastructure stopped."
fi

echo ""
echo "==> Final pod status:"
kubectl -n $NAMESPACE get pods
echo ""
echo "==> Services stopped."
