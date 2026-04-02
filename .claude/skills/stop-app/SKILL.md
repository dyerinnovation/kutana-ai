---
name: stop-app
description: Stop all Kutana AI services on the DGX Spark. TRIGGER on: stop app, stop services, shut down, bring down stack, halt kutana.
permissions:
  - Bash(ssh:*)
---

# Stop App

Stops all Kutana AI services on the DGX Spark.

## Usage

```bash
bash .claude/skills/stop-app/scripts/stop-app.sh
```

The script will:
1. SSH to DGX
2. Scale down all Kutana deployments to 0 replicas
3. Confirm pods are terminated
4. Leave infrastructure (postgres, redis) running unless `--full` flag is passed

## Full Stop (including infrastructure)

```bash
bash .claude/skills/stop-app/scripts/stop-app.sh --full
```
