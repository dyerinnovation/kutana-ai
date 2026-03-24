---
name: deploy
description: Deploy the latest code to the DGX Spark K3s cluster. TRIGGER on: deploy, push to DGX, update services, ship it, redeploy, rollout.
permissions:
  - Bash(ssh:*)
  - Bash(git:*)
  - Bash(rsync:*)
---

# Deploy

Deploys the latest code to the DGX Spark K3s cluster.

## Usage

```bash
bash .claude/skills/deploy/scripts/deploy.sh
```

## What it does

1. Rsync repo to DGX (excluding `.venv`, `node_modules`)
2. Build Docker images on DGX
3. Import images into containerd (`sudo k3s ctr images import`)
4. Apply updated K8s manifests / Helm chart upgrades
5. Roll out deployments and wait for pods to be Ready
6. Run health checks on all service endpoints
7. Print final status

## Flags

- `--service <name>` — deploy only one service (e.g. `--service api-server`)
- `--skip-build` — use existing images (faster, for config-only changes)
- `--dry-run` — show what would be deployed without making changes
