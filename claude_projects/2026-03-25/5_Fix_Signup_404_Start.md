# Fix Signup 404 — Plan Start

## Problem

`POST /api/v1/auth/register` returns 404. Sign-up is broken.

## Root Cause

The nginx ingress uses `rewrite-target: /$2` with path `/api(/|$)(.*)`, which strips the `/api` prefix before forwarding to the api-server. The api-server registers routes at `/api/v1/...` (via `prefix="/api/v1"` in `main.py`), so it receives `/v1/auth/register` but expects `/api/v1/auth/register`.

The health endpoint works because it's mounted without a prefix (`/health`), and the ingress rewrites `/api/health` → `/health`.

## Fix

Change `main.py` router prefix from `/api/v1` to `/v1`. The ingress provides the `/api` segment externally.

**File:** `services/api-server/src/api_server/main.py` — lines 57-63

Change all `prefix="/api/v1"` to `prefix="/v1"`.

## Affected Routes

All `/api/v1/*` routes:
- auth (register, login, me)
- meetings
- tasks
- agents
- agent_keys
- agent_templates
- token

## Verification

1. `curl -sk -X POST "https://kutana.spark-b0f2.local/api/v1/auth/register" -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"testpass123","name":"Test"}'` should return 201
2. `curl -sk "https://kutana.spark-b0f2.local/api/health"` should still return 200
