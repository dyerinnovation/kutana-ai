# Skill Alignment with K8s Deployment — Plan Start

## Objective
Fix Claude Code skills that have stale references after the Phase D K8s migration.

## Issues Found

1. **deploy.sh** — uses rsync + docker compose build instead of git + build_and_push.sh + local registry
2. **check-services.sh** — references `deployment/postgres` and `deployment/redis` (they're StatefulSets)
3. **wipe-data.sh** — same StatefulSet reference bug
4. **start-app.sh** — doesn't restart StatefulSets if stopped with `stop-app --full`

## Files Modified

- `.claude/skills/deploy/scripts/deploy.sh` — full rewrite
- `.claude/skills/deploy/SKILL.md` — removed invalid flags
- `.claude/skills/check-services/scripts/check-services.sh` — deployment → statefulset
- `.claude/skills/wipe-data/scripts/wipe-data.sh` — deployment → statefulset
- `.claude/skills/start-app/scripts/start-app.sh` — added StatefulSet scale-up before Deployment scale-up
