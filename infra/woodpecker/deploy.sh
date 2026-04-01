#!/usr/bin/env bash
# Deploy Woodpecker CI to the DGX Spark K3s cluster.
#
# Safe to re-run (idempotent). Does NOT apply secrets automatically —
# you must copy secrets.example.yaml → secrets.yaml and fill in real values first.
#
# Prerequisites:
#   1. kubectl configured and pointing at the DGX K3s cluster (already true on Mac mini)
#   2. Helm 3 installed locally
#   3. infra/woodpecker/secrets.yaml exists and is populated
#   4. woodpecker-ci Helm repo added (this script adds it if missing)
#
# Usage:
#   bash infra/woodpecker/deploy.sh
# ---------------------------------------------------------------------------
set -euo pipefail

NAMESPACE="woodpecker"
RELEASE="woodpecker"
CHART="woodpecker-ci/woodpecker"
VALUES_FILE="$(cd "$(dirname "$0")" && pwd)/values.yaml"
SECRETS_FILE="$(cd "$(dirname "$0")" && pwd)/secrets.yaml"
SECRETS_EXAMPLE="$(cd "$(dirname "$0")" && pwd)/secrets.example.yaml"

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
  echo "ERROR: infra/woodpecker/secrets.yaml not found."
  echo ""
  echo "  1. Copy the example:  cp ${SECRETS_EXAMPLE} ${SECRETS_FILE}"
  echo "  2. Fill in real values (GitHub OAuth client ID/secret, agent secret)"
  echo "  3. Re-run this script"
  echo ""
  exit 1
fi

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------
echo "==> Creating namespace '${NAMESPACE}' (if missing) ..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
echo "==> Applying woodpecker-secrets ..."
kubectl apply -f "$SECRETS_FILE"

# ---------------------------------------------------------------------------
# Create the woodpecker database in the convene postgres instance (if missing)
# ---------------------------------------------------------------------------
echo "==> Ensuring 'woodpecker' database exists in postgres ..."
if kubectl get pod -n convene -l app.kubernetes.io/name=postgres -o name 2>/dev/null | grep -q pod; then
  POSTGRES_POD=$(kubectl get pod -n convene -l app.kubernetes.io/name=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [[ -n "$POSTGRES_POD" ]]; then
    kubectl exec -n convene "$POSTGRES_POD" -- \
      psql -U convene -tc "SELECT 1 FROM pg_database WHERE datname='woodpecker'" \
      | grep -q 1 \
      || kubectl exec -n convene "$POSTGRES_POD" -- \
           psql -U convene -c "CREATE DATABASE woodpecker"
    echo "    OK — woodpecker database ready"
  else
    echo "    WARN: postgres pod not found in convene namespace — skipping DB create."
    echo "          Create the database manually: CREATE DATABASE woodpecker;"
  fi
else
  echo "    WARN: postgres not running yet — skipping DB create."
  echo "          Create the database manually after postgres is up."
fi

# ---------------------------------------------------------------------------
# Helm repo
# ---------------------------------------------------------------------------
echo "==> Adding woodpecker-ci Helm repo (if missing) ..."
if ! helm repo list 2>/dev/null | grep -q woodpecker-ci; then
  helm repo add woodpecker-ci https://woodpecker-ci.org/woodpecker-ci
fi
helm repo update woodpecker-ci

# ---------------------------------------------------------------------------
# Helm install / upgrade
# ---------------------------------------------------------------------------
echo "==> Installing/upgrading Woodpecker CI ..."
helm upgrade --install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  --values "$VALUES_FILE" \
  --wait \
  --timeout 5m

echo ""
echo "========================================"
echo "  Woodpecker CI deployed successfully"
echo "========================================"
echo ""
echo "  UI:   http://woodpecker.spark-b0f2.local"
echo "        (or your public Cloudflare Tunnel hostname)"
echo ""
echo "  Next steps:"
echo "    1. Open the Woodpecker UI and log in with your GitHub account"
echo "    2. Enable the dyerinnovation/convene-ai repository"
echo "    3. Push a commit to main to trigger the first pipeline run"
echo ""
