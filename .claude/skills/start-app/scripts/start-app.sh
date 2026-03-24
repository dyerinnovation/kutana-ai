#!/usr/bin/env bash
# Start all Convene AI services on the DGX Spark K3s cluster
set -euo pipefail

NAMESPACE=convene
DGX=dgx

echo "==> Checking K3s cluster health..."
ssh "$DGX" 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get nodes'

echo ""
echo "==> Scaling up all Convene deployments..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE scale deployment --all --replicas=1"

echo ""
echo "==> Waiting for pods to be Ready..."
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE wait --for=condition=ready pod --all --timeout=120s"

echo ""
echo "==> Pod status:"
ssh "$DGX" "echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n $NAMESPACE get pods"

echo ""
echo "==> Health checks..."
BASE="https://convene.spark-b0f2.local"
curl -sk "$BASE/api/health" && echo "  API: OK" || echo "  API: FAIL"
curl -sk -o /dev/null -w "  Frontend: %{http_code}\n" "$BASE/"

echo ""
echo "==> Services are up!"
echo "    Frontend/API: $BASE"
echo "    MCP server:   $BASE/mcp"
echo "    Agent gateway: wss://convene.spark-b0f2.local/ws"
