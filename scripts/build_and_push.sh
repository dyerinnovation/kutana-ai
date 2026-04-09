#!/usr/bin/env bash
# Build and push Docker images to the local K3s registry.
# Usage: bash scripts/build_and_push.sh all
#        bash scripts/build_and_push.sh api-server agent-gateway
#
# Must run on the DGX Spark (hostname contains "spark").
set -euo pipefail

REGISTRY="localhost:30500/kutana"
REPO_DIR="$HOME/kutana-ai"

ALL_SERVICES=(api-server agent-gateway audio-service task-engine mcp-server worker web)

# ---------------------------------------------------------------------------
# Validate environment
# ---------------------------------------------------------------------------
if [[ "$(hostname)" != *spark* ]]; then
  echo "ERROR: This script must run on the DGX Spark (hostname contains 'spark')."
  echo "       Current hostname: $(hostname)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
if [[ $# -eq 0 ]]; then
  echo "Usage: $0 all | <service1> [service2 ...]"
  echo "Services: ${ALL_SERVICES[*]}"
  exit 1
fi

if [[ "$1" == "all" ]]; then
  SERVICES=("${ALL_SERVICES[@]}")
else
  SERVICES=("$@")
fi

# ---------------------------------------------------------------------------
# Pull latest code
# ---------------------------------------------------------------------------
echo "==> Pulling latest code in $REPO_DIR ..."
cd "$REPO_DIR"
git pull

# ---------------------------------------------------------------------------
# Build & push each service
# ---------------------------------------------------------------------------
FAILED=()
SUCCEEDED=()

for svc in "${SERVICES[@]}"; do
  BUILD_ARGS=()
  if [[ "$svc" == "web" ]]; then
    DOCKERFILE="web/Dockerfile"
    # Vite env vars for production build. Override in env if needed.
    BUILD_ARGS+=(--build-arg "VITE_API_BASE_URL=${VITE_API_BASE_URL:-https://api-dev.kutana.ai/v1}")
    BUILD_ARGS+=(--build-arg "VITE_WS_BASE_URL=${VITE_WS_BASE_URL:-https://ws-dev.kutana.ai}")
  elif [[ "$svc" == "eval" ]]; then
    DOCKERFILE="evals/Dockerfile"
  else
    DOCKERFILE="services/${svc}/Dockerfile"
  fi
  TAG="${REGISTRY}/${svc}:latest"

  if [[ ! -f "$DOCKERFILE" ]]; then
    echo "ERROR: Dockerfile not found: $DOCKERFILE"
    FAILED+=("$svc")
    continue
  fi

  echo ""
  echo "==> Building $svc ..."
  START_TIME=$(date +%s)

  if docker build -t "$TAG" "${BUILD_ARGS[@]}" -f "$DOCKERFILE" . ; then
    echo "==> Pushing $svc ..."
    if docker push "$TAG" ; then
      END_TIME=$(date +%s)
      ELAPSED=$(( END_TIME - START_TIME ))
      echo "    $svc succeeded in ${ELAPSED}s"
      SUCCEEDED+=("$svc")
    else
      echo "    ERROR: push failed for $svc"
      FAILED+=("$svc")
    fi
  else
    echo "    ERROR: build failed for $svc"
    FAILED+=("$svc")
  fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  Build & Push Summary"
echo "========================================"
if [[ ${#SUCCEEDED[@]} -gt 0 ]]; then
  echo "  Succeeded: ${SUCCEEDED[*]}"
fi
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "  FAILED:    ${FAILED[*]}"
  exit 1
fi
echo "  All services built and pushed successfully."
