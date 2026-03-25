---
name: build-and-push
description: Build and push Docker images to the local K3s registry. Usage: /build-and-push [all | service1 service2 ...]. TRIGGER when user says build images, push images, build and push, rebuild services.
permissions:
  - Bash(ssh:*)
  - Bash(git:*)
---

# Build and Push

Builds Docker images for Convene AI services and pushes them to the local K3s registry on the DGX Spark.

## Steps

1. **Ensure code is committed and pushed to GitHub:**
   - Run `git status` to check for uncommitted changes
   - If there are changes, warn the user and ask if they want to commit first
   - Run `git push` to ensure the remote is up to date

2. **SSH to DGX and run the build script:**
   ```bash
   ssh dgx 'cd ~/convene-ai && bash scripts/build_and_push.sh <args>'
   ```
   Where `<args>` is either `all` or the specific service names provided by the user.

3. **Report results:**
   - Show which services succeeded and failed
   - Show build timing per service
   - If any failed, suggest checking the Dockerfile and logs

## Available Services

- `api-server` — REST API (port 8000)
- `agent-gateway` — WebSocket gateway (port 8003)
- `audio-service` — Audio pipeline (port 8001)
- `task-engine` — Task extraction (port 8002)
- `mcp-server` — MCP tools server (port 3001)

## Examples

```
/build-and-push all
/build-and-push api-server agent-gateway
/build-and-push mcp-server
```
