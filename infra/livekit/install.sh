#!/usr/bin/env bash
# Deploy the official LiveKit Helm chart to the DGX Spark K3s cluster.
#
# Safe to re-run (idempotent). Does NOT create secrets automatically —
# you must create the livekit-credentials K8s secret first.
# See infra/livekit/secrets.example.yaml for instructions.
#
# Chart:   livekit/livekit-server
# Repo:    https://helm.livekit.io
#
# Prerequisites:
#   1. kubectl configured and pointing at the DGX K3s cluster (already true on Mac mini)
#   2. Helm 3 installed locally
#   3. livekit-credentials K8s secret exists in the kutana namespace
#
# Usage:
#   bash infra/livekit/install.sh
# ---------------------------------------------------------------------------
set -euo pipefail

NAMESPACE="kutana"
RELEASE="livekit-server"
CHART="livekit/livekit-server"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALUES_FILE="${SCRIPT_DIR}/values.yaml"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
echo "==> Checking prerequisites ..."

if ! command -v kubectl &>/dev/null; then
  echo "ERROR: kubectl not found. Install it and configure ~/.kube/config."
  exit 1
fi

if ! command -v helm &>/dev/null; then
  echo "ERROR: helm not found. Install Helm 3."
  exit 1
fi

if ! kubectl get secret livekit-credentials -n "$NAMESPACE" &>/dev/null; then
  echo ""
  echo "ERROR: K8s secret 'livekit-credentials' not found in namespace '${NAMESPACE}'."
  echo ""
  echo "  Create it first (see infra/livekit/secrets.example.yaml for details):"
  echo ""
  echo "    kubectl create secret generic livekit-credentials \\"
  echo "      --namespace ${NAMESPACE} \\"
  echo "      --from-literal=api-key-1=YOUR_API_KEY \\"
  echo "      --from-literal=api-secret-1=YOUR_API_SECRET"
  echo ""
  exit 1
fi

# ---------------------------------------------------------------------------
# Helm repo
# ---------------------------------------------------------------------------
echo "==> Adding livekit Helm repo (if missing) ..."
helm repo add livekit https://helm.livekit.io 2>/dev/null || true
helm repo update livekit

# ---------------------------------------------------------------------------
# Helm install / upgrade
# ---------------------------------------------------------------------------
echo "==> Installing/upgrading LiveKit server into namespace '${NAMESPACE}' ..."
helm upgrade --install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" \
  --values "$VALUES_FILE" \
  --wait \
  --timeout 10m

echo ""
echo "========================================"
echo "  LiveKit server deployed successfully"
echo "========================================"
echo ""
echo "  Verify deployment:"
echo "    kubectl get pods -n ${NAMESPACE} -l app=${RELEASE}"
echo "    kubectl logs -n ${NAMESPACE} deploy/${RELEASE}"
echo ""
echo "  Service endpoint (in-cluster):"
echo "    livekit-server.${NAMESPACE}.svc.cluster.local:7880"
echo ""
echo "  Next steps:"
echo "    1. Update kutana-secret with LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET"
echo "    2. Redeploy api-server and agent-gateway to pick up LiveKit config"
echo "    3. Store credentials in ~/Documents/dev/z-api-keys-and-tokens/livekit-credentials.md"
echo ""
