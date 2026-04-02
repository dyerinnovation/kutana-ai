---
name: wipe-data
description: Wipe all Kutana AI data — drop and recreate the database, flush Redis. TRIGGER on: wipe data, reset database, clean slate, flush redis, drop database, reset state.
permissions:
  - Bash(ssh:*)
---

# Wipe Data

**Destructive.** Drops the Postgres database, recreates it, runs migrations, and flushes Redis.

Always confirm with the user before running this.

## Usage

```bash
bash .claude/skills/wipe-data/scripts/wipe-data.sh
```

Options:
- `--seed` — re-seed with test data after wipe
- `--redis-only` — only flush Redis, leave Postgres intact
- `--db-only` — only drop/recreate Postgres, leave Redis intact

## What it does

1. Drops `kutana` database on DGX postgres pod
2. Recreates the database
3. Runs `alembic upgrade head`
4. Flushes all Redis keys with `FLUSHALL`
5. Optionally seeds test users and a sample meeting
