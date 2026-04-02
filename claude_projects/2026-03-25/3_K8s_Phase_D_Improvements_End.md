# K8s Phase D Improvements — Plan End

## Work Completed

- **Deleted stale test_multi_agent.pyc** — source file was already removed, cleaned up orphaned cache
- **Fixed alembic migration Job** — changed `DATABASE_URL_SYNC` → `DATABASE_URL` in migrate-job.yaml. Root cause: `alembic/env.py` uses `async_engine_from_config` which requires `postgresql+asyncpg://`, not the plain sync URL. Helm upgrade now runs hooks successfully.
- **Deployed web frontend to K8s**:
  - Created `web/Dockerfile` (multi-stage: node:22-slim build + nginx:1.27-alpine serve)
  - Created `web/nginx.conf` (SPA fallback, gzip, cache headers for hashed assets)
  - Created `charts/kutana/templates/deployment-web.yaml` and `service-web.yaml`
  - Added separate catch-all `/` Ingress in `ingress.yaml` (Prefix type, no rewrite — avoids conflict with regex rewrite on API routes)
  - Added `web:` section to `values.yaml` (50m/64Mi requests, 200m/128Mi limits)
  - Updated `scripts/build_and_push.sh` — added `web` to ALL_SERVICES with special-case Dockerfile path
  - Fixed build failure: `manifest.ts` imports `external-docs/` at build time — Dockerfile now copies `external-docs/` to `/repo/external-docs/` to maintain relative path structure
- **Deployed OTel Collector Agent DaemonSet** (`infra/k8s/otel-agent.yaml`):
  - ServiceAccount, ClusterRole (pods/namespaces RBAC), ClusterRoleBinding
  - ConfigMap with filelog receiver → k8sattributes processor → batch → OTLP exporter
  - DaemonSet running `otel/opentelemetry-collector-contrib:0.96.0`

## Work Remaining

- **SigNoz OTel collector not accepting OTLP connections** — The SigNoz collector's OTLP gRPC receiver (port 4317) is refusing connections. The collector uses OpAmp management and the OpAmp server keeps returning errors. The OTel agent DaemonSet is deployed and retrying — it will auto-connect when the collector issue is resolved. This appears to be a pre-existing SigNoz installation issue, not related to our agent config.
  - Potential fix: Reinstall SigNoz with the latest Helm chart, or configure the collector to not rely on OpAmp for startup
  - Alternative: Switch the agent's exporter to target SigNoz's HTTP log receiver on port 8082 (logsjson)

## Lessons Learned

- **Vite imports outside project dir**: When `manifest.ts` imports `../../../external-docs/`, the Docker build context must include `external-docs/` and the WORKDIR must maintain the relative path structure (used `/repo/web` as WORKDIR, copied `external-docs/` to `/repo/external-docs/`)
- **Ingress rewrite conflict**: The existing Ingress uses `rewrite-target: /$2` with regex capture groups. A catch-all `/` route can't use the same rewrite. Solution: create a separate Ingress resource with `pathType: Prefix` (no rewrite annotation) — Prefix matches have lower specificity than regex matches.
- **Migration Job sync vs async URL**: alembic `env.py` can use either sync or async engines, but ours is configured for async only. The configmap has both URLs — make sure to use the correct one.
- **SigNoz OpAmp**: The SigNoz custom collector binary uses OpAmp for remote configuration management. If the OpAmp server (signoz-0 pod) can't deliver config, the collector may not start its receivers. This is different from a vanilla OTel collector which just reads config.yaml.
- **Helm chart path on DGX**: When running helm via SSH, use full path to the chart directory (`~/kutana-ai/charts/kutana`), not relative paths.

## Commits

1. `b6f7306` — feat: Phase D — web frontend deploy, OTel agent, migration fix
2. `cfb6ef1` — fix: copy external-docs into web Docker build context
