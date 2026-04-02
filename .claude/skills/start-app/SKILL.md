---
name: start-app
description: Start the Kutana AI application on the DGX Spark. TRIGGER on: start app, start services, start kutana, launch app, bring up services, start the stack.
permissions:
  - Bash(ssh:*)
  - Bash(scp:*)
---

# Start App

Starts all Kutana AI services on the DGX Spark via K3s/Kubernetes.

## Usage

Run the start script:

```bash
bash .claude/skills/start-app/scripts/start-app.sh
```

The script will:
1. SSH to DGX and check K3s cluster health
2. Start infrastructure (postgres, redis) if not running
3. Roll out all service deployments
4. Run health checks on each endpoint
5. Print the live cluster URLs

## Service URLs (after start)

- Frontend + API: `https://kutana.spark-b0f2.local`
- API health: `https://kutana.spark-b0f2.local/api/health`
- MCP server: `https://kutana.spark-b0f2.local/mcp`
- Agent gateway: `wss://kutana.spark-b0f2.local/ws`
