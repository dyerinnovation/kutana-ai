# Fix Migration Hook + Speaker Names + Docker Best Practices — Plan Start

## Problem
1. Helm migration hook fails — stale Docker image missing latest alembic revision `d5e6f7a8b9c0`
2. Transcript shows "speaker_0" instead of participant's display name
3. All Python service Dockerfiles use `COPY . .` (entire monorepo) — no multi-stage builds

## Plan
1. Thread `speaker_name` from human session through audio pipeline to frontend (9 files)
2. Rewrite all 5 Python service Dockerfiles as multi-stage builds (builder + runtime)
3. Add `.dockerignore` to exclude non-essential files
4. api-server image includes `alembic.ini` + `alembic/` for migration hook
5. Rebuild all images, deploy, verify migration hook + speaker names
