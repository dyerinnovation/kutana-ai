#!/usr/bin/env bash
# Deploy the official Langfuse Helm chart to the DGX Spark K3s cluster.
#
# Safe to re-run (idempotent). Does NOT apply secrets automatically —
# you must copy secrets.example.yaml → secrets.yaml and fill in real values first.
#
# Chart:   oci://ghcr.io/langfuse/langfuse-k8s/charts/langfuse
# Version: 1.5.25 (Langfuse server 3.167.1)
#
# Prerequisites:
#   1. kubectl configured and pointing at the DGX K3s cluster (already true on Mac mini)
#   2. Helm 3 installed locally with OCI registry support
#   3. infra/langfuse/secrets.yaml exists and is populated
#
# Usage:
#   bash infra/langfuse/install.sh
# ---------------------------------------------------------------------------
set -euo pipefail

NAMESPACE="kutana"
RELEASE="langfuse"
CHART="oci://ghcr.io/langfuse/langfuse-k8s/charts/langfuse"
CHART_VERSION="1.5.25"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALUES_FILE="${SCRIPT_DIR}/values.yaml"
SECRETS_FILE="${SCRIPT_DIR}/secrets.yaml"
SECRETS_EXAMPLE="${SCRIPT_DIR}/secrets.example.yaml"

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

if [[ ! -f "$SECRETS_FILE" ]]; then
  echo ""
  echo "ERROR: infra/langfuse/secrets.yaml not found."
  echo ""
  echo "  1. Copy the example:  cp ${SECRETS_EXAMPLE} ${SECRETS_FILE}"
  echo "  2. Fill in real values (salt, nextauth secret, encryption key, passwords, S3 keys)"
  echo "  3. Re-run this script"
  echo ""
  exit 1
fi

# ---------------------------------------------------------------------------
# Helm install / upgrade
# ---------------------------------------------------------------------------
echo "==> Installing/upgrading Langfuse (${CHART_VERSION}) into namespace '${NAMESPACE}' ..."
helm upgrade --install "$RELEASE" "$CHART" \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  --values "$VALUES_FILE" \
  --values "$SECRETS_FILE" \
  --wait \
  --timeout 10m

echo ""
echo "========================================"
echo "  Langfuse deployed successfully"
echo "========================================"
echo ""
echo "  UI:  http://langfuse.spark-b0f2.local"
echo "       (port-forward: kubectl port-forward -n kutana svc/langfuse-web 3000:3000)"
echo ""
echo "  Next steps:"
echo "    1. Open the Langfuse UI and create an admin user"
echo "    2. Create a project (e.g. 'kutana-dev')"
echo "    3. Mint a new public + secret key pair from project settings"
echo "    4. Update ~/Documents/dev/z-api-keys-and-tokens/langfuse-credentials.md"
echo "    5. Rotate keys in kutana-secret and redeploy api-server"
echo ""
