#!/bin/bash
set -e

# Convene AI — Deploy to DGX Spark
# Usage: ./deploy/deploy-to-dgx.sh
# Run this from your Mac. It will SSH into the DGX and set everything up.

DGX_HOST="jondyer3@spark-b0f2.local"
REPO_DIR="$HOME/convene-ai"
REMOTE_URL="git@github.com:dyerinnovation/convene-ai.git"

echo "=== Deploying Convene AI to DGX Spark ==="

# Step 1: Check if repo exists on DGX, if not clone it
echo "[1/6] Setting up repo on DGX..."
ssh $DGX_HOST "
  if [ -d $REPO_DIR ]; then
    echo 'Repo exists, pulling latest...'
    cd $REPO_DIR && git pull
  else
    echo 'Cloning repo...'
    git clone $REMOTE_URL $REPO_DIR
  fi
"

# Step 2: Copy .env with API keys
echo "[2/6] Copying .env configuration..."
scp "$(dirname "$0")/../.env" "$DGX_HOST:$REPO_DIR/.env"

# Step 3: Check Docker is available
echo "[3/6] Checking Docker on DGX..."
ssh $DGX_HOST "
  if command -v docker &>/dev/null; then
    echo 'Docker found:' \$(docker --version)
    echo 'Docker Compose:' \$(docker compose version 2>/dev/null || echo 'not found')
  else
    echo 'ERROR: Docker not found on DGX. Installing...'
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker \$USER
    echo 'Docker installed. You may need to log out and back in for group changes.'
  fi
"

# Step 4: Build and start the stack
echo "[4/6] Building and starting services..."
ssh $DGX_HOST "
  cd $REPO_DIR
  docker compose up -d --build 2>&1
"

# Step 5: Wait for services to come up
echo "[5/6] Waiting for services to start..."
sleep 10
ssh $DGX_HOST "
  cd $REPO_DIR
  docker compose ps
  echo ''
  echo 'Checking service health...'
  for svc in postgres redis api-server agent-gateway audio-service task-engine mcp-server; do
    status=\$(docker compose ps --format '{{.State}}' \$svc 2>/dev/null)
    echo \"  \$svc: \$status\"
  done
"

# Step 6: Get the DGX IP and print connection info
echo "[6/6] Getting connection info..."
DGX_IP=$(ssh $DGX_HOST "hostname -I | awk '{print \$1}'")
echo ""
echo "=== Deployment Complete ==="
echo ""
echo "  API Server:      http://$DGX_IP:8000"
echo "  Agent Gateway:   ws://$DGX_IP:8003"
echo "  Audio Service:   http://$DGX_IP:8001"
echo "  Task Engine:     http://$DGX_IP:8002"
echo "  MCP Server:      http://$DGX_IP:3001"
echo ""
echo "  To run pipeline test:"
echo "    ssh $DGX_HOST 'cd $REPO_DIR && python3 examples/test-pipeline.py'"
echo ""
echo "  To run demo agent:"
echo "    ssh $DGX_HOST 'cd $REPO_DIR/examples/demo-agent && python3 agent.py --meeting-id <id>'"
echo ""
echo "  To view logs:"
echo "    ssh $DGX_HOST 'cd $REPO_DIR && docker compose logs -f'"
