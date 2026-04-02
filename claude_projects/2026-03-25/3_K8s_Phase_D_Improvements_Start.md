# K8s Phase D Improvements — Plan Start

## Objective
Complete the final 3 tasks of the K8s migration plus fix the alembic migration Job.

## Tasks

### Task 8: Wire SigNoz OTel Collector for Pod Logs
- Deploy OTel Collector Agent DaemonSet with filelog receiver
- Scrapes /var/log/pods/ and forwards to existing SigNoz collector
- Zero code changes to Python services
- File: `infra/k8s/otel-agent.yaml`

### Task 9: Delete Stale test_multi_agent.pyc
- Source file already deleted, only .pyc remains
- Delete cache file, verify tests pass

### Task 10: Web Frontend K8s Deployment
- `web/Dockerfile` — multi-stage node:22-slim + nginx:1.27-alpine
- `web/nginx.conf` — SPA routing, gzip, cache headers
- `charts/kutana/templates/deployment-web.yaml` — Deployment
- `charts/kutana/templates/service-web.yaml` — ClusterIP Service
- `charts/kutana/templates/ingress.yaml` — Add catch-all `/` route (separate Ingress, Prefix type)
- `charts/kutana/values.yaml` — Add web section
- `scripts/build_and_push.sh` — Add web to ALL_SERVICES with special-case Dockerfile path

### Migration Job Fix
- `charts/kutana/templates/migrate-job.yaml` — Change DATABASE_URL_SYNC → DATABASE_URL
- Root cause: alembic/env.py uses async_engine_from_config (needs postgresql+asyncpg://)

## Deployment Steps
1. Git push + pull on DGX
2. Build web image: `scripts/build_and_push.sh web`
3. Helm upgrade (without --no-hooks)
4. Deploy OTel agent to signoz namespace
5. Verify: all pods running, browser loads SPA, SigNoz shows logs
