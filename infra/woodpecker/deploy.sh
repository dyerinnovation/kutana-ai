#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=woodpecker
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Ensuring namespace exists..."
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

echo "Applying secrets..."
kubectl apply -f "$SCRIPT_DIR/secrets.yaml"

echo "Deploying Woodpecker via Helm..."
helm upgrade --install woodpecker woodpecker/woodpecker \
  --namespace "$NAMESPACE" \
  --values "$SCRIPT_DIR/values.yaml" \
  --wait \
  --timeout 5m

echo "Woodpecker deployed. Pod status:"
kubectl get pods -n "$NAMESPACE"

echo ""
echo "Server ingress:"
kubectl get ingress -n "$NAMESPACE"
