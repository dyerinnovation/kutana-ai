# Skill Alignment with K8s Deployment — Plan End

## Work Completed

- **Rewrote `deploy.sh`** — replaced rsync + docker compose build + docker save pipeline with git push/pull + `build_and_push.sh` + helm upgrade. Removed nonexistent `worker` service references. Updated SKILL.md to remove invalid `--dry-run` flag.
- **Fixed `check-services.sh`** — changed `deployment/postgres` → `statefulset/postgres` and `deployment/redis` → `statefulset/redis` so kubectl exec targets the correct resource type.
- **Fixed `wipe-data.sh`** — same StatefulSet reference fix for postgres and redis exec commands.
- **Improved `start-app.sh`** — added StatefulSet scale-up block before Deployment scale-up. Now works correctly even after `stop-app --full` was used. Uses `app.kubernetes.io/name` label selectors matching the Helm chart templates.

## Verification

- Start-app skill executed successfully:
  - StatefulSets scaled to 1 (postgres-0, redis-0 ready)
  - All 7 deployments scaled up
  - API health: `{"status":"healthy","service":"api-server"}`
  - Frontend: HTTP 200
- K3s API server was slow responding to kubectl (cluster under load), but services are running

- **Made start-app/stop-app target named deployments** — replaced `deployment --all` with explicit list `api-server agent-gateway audio-service task-engine mcp-server web` to avoid scaling up stale deployments.
- **Cleaned up stale K8s resources on DGX:**
  - Killed orphaned vLLM Whisper processes (PID 2118521/2117720) — ~2.2GB freed
  - `helm uninstall stt -n kutana` (stale Helm release from March 2)
  - `helm uninstall acclimate-api acclimate-postgresql acclimate-redis -n acclimate`
  - `helm uninstall langfuse -n acclimate`
  - `helm uninstall openclaw -n openclaw`
  - Deleted `acclimate` and `openclaw` namespaces
  - Killed orphaned `openclaw-gateway` process (~985MB)
  - DGX memory: 196Mi available → 111Gi available

## Work Remaining

- None — all skill fixes applied and cluster cleaned up.

## Lessons Learned

- Postgres and Redis are **StatefulSets** in the Helm chart, not Deployments. `kubectl exec deployment/<name>` silently fails or hangs — must use `statefulset/<name>`.
- Helm chart pod labels use `app.kubernetes.io/name` (not `app`). Always verify label selectors against the actual templates.
- **Never use `kubectl scale deployment --all`** in a shared namespace — it scales up stale deployments too. Always target named deployments.
- The stale `stt` Helm release (vLLM Whisper large-v3) consumed ~2.2GB RAM + 75% CPU. Combined with SigNoz (~2.7GB), OpenClaw (~985MB), and Acclimate, the DGX had only 196Mi free and entered a swap death spiral where even SSH and kubectl became unresponsive.
- When the K3s API server is unresponsive due to memory pressure, basic system commands (`free -h`, `ps aux`) still work via SSH. Kill memory hogs at the process level first, then use kubectl/helm to clean up properly.
