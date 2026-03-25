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
   ssh dgx 'cd ~/convene-ai && git pull'
   ```

3. **Build and push images (if needed):**
   ```bash
   ssh dgx 'cd ~/convene-ai && bash scripts/build_and_push.sh all'
   ```

4. **Deploy via Helm:**
   ```bash
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm upgrade --install convene charts/convene -n convene'
   ```

5. **Wait for pods and check status:**
   ```bash
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout status -n convene deploy/api-server --timeout=120s'
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n convene'
   ```

6. **Report final status**

## Flags

- Pass a service name as the first argument to deploy only that service (e.g. `bash deploy.sh api-server`)
- Set `SKIP_BUILD=1` env var to skip image builds (faster, for config-only changes)
