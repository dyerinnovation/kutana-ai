---
name: deploy
description: Deploy the latest code to the DGX Spark K3s cluster. TRIGGER on: deploy, push to DGX, update services, ship it, redeploy, rollout.
permissions:
  - Bash(ssh:*)
  - Bash(git:*)
---

# Deploy

Deploys the latest code to the DGX Spark K3s cluster using git + Helm.

## Steps

1. **Ensure code is committed and pushed to GitHub:**
   - Run `git status` to check for uncommitted changes
   - If there are changes, warn the user and ask if they want to commit first
   - Run `git push` to ensure the remote is up to date

2. **Pull latest code on DGX:**
   ```bash
   ssh dgx 'cd ~/kutana-ai && git pull'
   ```

3. **Build and push images (if needed):**
   ```bash
   ssh dgx 'cd ~/kutana-ai && bash scripts/build_and_push.sh all'
   ```

4. **Deploy via Helm (runs locally — kubectl/helm configured to target DGX Spark):**
   ```bash
   helm upgrade --install kutana charts/kutana -n kutana --create-namespace
   ```

5. **Wait for pods and check status:**
   ```bash
   kubectl rollout status -n kutana deploy/api-server --timeout=120s
   kubectl get pods -n kutana
   ```

6. **Report final status**

## Flags

- Pass a service name as the first argument to deploy only that service (e.g. `bash deploy.sh api-server`)
- Set `SKIP_BUILD=1` env var to skip image builds (faster, for config-only changes)
