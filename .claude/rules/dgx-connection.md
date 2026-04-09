# DGX Spark Connection Rules

Image builds run on the DGX Spark. kubectl/helm run locally — they are configured to connect directly to the DGX K3s cluster.

## Code Sync (git-based, NOT rsync)

```bash
# Push locally, then pull on DGX
git push
ssh dgx 'cd ~/kutana-ai && git pull'
```

## Build & Push Images

Use the `/build-and-push` skill or run directly:
```bash
ssh dgx 'cd ~/kutana-ai && bash scripts/build_and_push.sh all'
ssh dgx 'cd ~/kutana-ai && bash scripts/build_and_push.sh api-server agent-gateway'
```

## Deploy (Helm — runs locally)

kubectl and helm are configured locally to target the DGX K3s cluster. No SSH required:

```bash
helm upgrade --install kutana charts/kutana -n kutana --create-namespace
```

## Cluster Status & Logs (run locally)

```bash
# Pod status
kubectl get pods -n kutana

# Service logs
kubectl logs -n kutana deploy/agent-gateway

# Helm releases
helm list -A
```

## SSH Patterns

SSH is still used for git pull and image builds (which run on DGX):

```bash
ssh dgx '<command>'
```

## Langfuse (LLM Observability)

- **UI:** `http://langfuse.spark-b0f2.local` — login: `admin@kutana.ai`
- **Credentials:** `~/Documents/dev/z-api-keys-and-tokens/langfuse-credentials.md`
- **Public Key:** `pk-lf-77c5dc94-c77b-49a8-8db4-2b5cacf27ca2`
- **In-cluster host:** `http://langfuse.kutana.svc:3000`

## Key Facts

- **kubectl/helm:** configured locally via `~/.kube/config` — run them directly, no SSH needed
- **Image builds:** still happen on DGX via `ssh dgx 'bash scripts/build_and_push.sh ...'`
- **Container runtime:** containerd (K3s) — local Docker registry at `localhost:30500`
- **Cluster URLs:** `kutana.spark-b0f2.local` — use `aiohttp` not `httpx` for mDNS
- **Docker Compose:** can still be used for local dev but is NOT the production deployment method
- See `internal-docs/architecture/patterns/dgx-spark-ssh.md` for full patterns.
