# Woodpecker CI — Setup Status

**Status:** Paused. Continuing with normal deploy process for now.

**Last updated:** 2026-04-01

---

## What Was Completed

- **Cloudflare Tunnel** — `cloudflared` installed and running on DGX as a systemd service (`convene-dgx` tunnel, ID `aeac4d94-0e1a-468c-afb1-4e6ff055c666`). Running with token-based auth.
- **Tailscale** — installed and authenticated on DGX (IP: 100.127.84.30).
- **GitHub OAuth App** — created at https://github.com/settings/developers:
  - Application name: Woodpecker CI
  - Homepage URL: https://ci.convene.ai
  - Callback URL: https://ci.convene.ai/authorize
  - Credentials stored in `z-api-keys-and-tokens/convene-github-oauth.md`
- **Woodpecker K8s namespace** — created (subsequently deleted, see below).
- **Woodpecker database** — created in the existing PostgreSQL instance (`woodpecker` database, accessed via `convene` user).
- **Helm repo** — `woodpecker` repo added (`https://woodpecker-ci.org/`).
- **Agent secret generated** — `5e4eabba5328b5553c2ffe539c235930`
- **infra/woodpecker/** — created with `secrets.yaml`, `values.yaml`, `deploy.sh`. Woodpecker Helm chart was deployed and pods came up healthy.
- **K8s Ingress** — configured for `ci.convene.ai` → `woodpecker-server:80` via ingress-nginx.

## What Remains

- **Cloudflare tunnel routing** — `convene.ai` is not a zone on the Cloudflare account that manages the tunnel (`Dyercapital.innovationstation@gmail.com`). Without the domain in that account, the "Published application" route form can't auto-create the DNS record. Options:
  1. Add `convene.ai` as a zone to the tunnel's Cloudflare account, then add a Published Application route (`ci` → `http://192.168.8.203:80`).
  2. Manually add a CNAME record (`ci` → `aeac4d94-0e1a-468c-afb1-4e6ff055c666.cfargotunnel.com`) in whichever Cloudflare account manages `convene.ai` DNS.
- **Deploy skill** — update `/deploy` and `/build-and-push` skills to run tests via Woodpecker instead of direct SSH.
- **End-to-end verification** — confirm GitHub OAuth login works, activate convene-ai repo in Woodpecker, test that a push triggers a pipeline.
- **`.woodpecker.yml`** — review pipeline steps for the GL-BE3600 network (DGX now at 192.168.8.203).

## Cleanup Performed

- Woodpecker Helm release uninstalled.
- `woodpecker` K8s namespace deleted.
- cloudflared config files removed from DGX (`/etc/cloudflared/config.yml`, credentials JSON).
- cloudflared reverted to original token-based systemd service (no local ingress config).
- `infra/woodpecker/` files retained in repo for future resumption.

## Infrastructure Files

| File | Purpose |
|------|---------|
| `infra/woodpecker/secrets.yaml` | K8s Secret — OAuth credentials, agent secret, DB connection string |
| `infra/woodpecker/values.yaml` | Helm values — server host, GitHub forge, ingress, agent config |
| `infra/woodpecker/deploy.sh` | One-command deploy: applies secrets + `helm upgrade --install` |

## To Resume

```bash
# 1. Resolve DNS (see above)

# 2. Redeploy
bash infra/woodpecker/deploy.sh

# 3. Verify
kubectl get pods -n woodpecker
curl -s https://ci.convene.ai/healthz
```
