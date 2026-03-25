# DGX Spark Connection Rules

All builds, deployments, and heavy compute run on the DGX Spark K3s cluster — not the local Mac.

## Code Sync (git-based, NOT rsync)

```bash
# Push locally, then pull on DGX
git push
ssh dgx 'cd ~/convene-ai && git pull'
```

## Build & Push Images

Use the `/build-and-push` skill or run directly:
```bash
ssh dgx 'cd ~/convene-ai && bash scripts/build_and_push.sh all'
ssh dgx 'cd ~/convene-ai && bash scripts/build_and_push.sh api-server agent-gateway'
```

## Deploy (Helm)

```bash
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm upgrade --install convene charts/convene -n convene'
```

## Cluster Status & Logs

```bash
# Pod status
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -n convene'

# Service logs
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl logs -n convene deploy/agent-gateway'

# Helm releases
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm list -A'
```

## SSH Patterns

**Regular commands (no password — key auth):**
```bash
ssh dgx '<command>'
```

**Sudo commands (pipe password for sudo only):**
```bash
ssh dgx 'echo JDf33nawm3! | sudo -S <command>'
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl <cmd>'
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm <cmd>'
```

## Key Facts

- **Container runtime:** containerd (K3s) — local Docker registry at `localhost:30500`
- **KUBECONFIG:** `/etc/rancher/k3s/k3s.yaml` — always pass explicitly via `sudo env KUBECONFIG=...`
- **Helm full path:** `/home/jondyer3/.local/bin/helm` — sudo does not inherit PATH
- **Cluster URLs:** `convene.spark-b0f2.local` — use `aiohttp` not `httpx` for mDNS
- **Docker Compose:** can still be used for local dev but is NOT the production deployment method
- See `internal-docs/architecture/patterns/dgx-spark-ssh.md` for full patterns.
