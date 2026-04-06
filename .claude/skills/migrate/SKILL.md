---
name: migrate
description: Run or create Alembic database migrations against the DGX K3s PostgreSQL. TRIGGER on: migrate, migration, alembic, database migration, run migration, create migration, schema change.
permissions:
  - Bash(kubectl:*)
  - Bash(ssh:*)
---

# Alembic Database Migrations

Run or create Alembic migrations for the Kutana PostgreSQL database running in K3s.

## Key Facts

- **Alembic config:** `alembic.ini` at repo root
- **Migrations dir:** `alembic/versions/`
- **env.py:** `alembic/env.py` — async (asyncpg), imports models from `kutana_core.database.models`
- **ORM models:** `packages/kutana-core/src/kutana_core/database/models.py`
- **Database:** PostgreSQL in K3s at `postgres.kutana.svc:5432/kutana` (user: `kutana`, pass: `kutana`)
- **Alembic runs inside the api-server pod** — K3s cluster DNS is only resolvable from within the cluster. Never try to run Alembic from the DGX host or locally.

## Check Current Migration State

```bash
kubectl exec -n kutana deploy/api-server -- python -m alembic current
```

## Apply Pending Migrations

```bash
kubectl exec -n kutana deploy/api-server -- python -m alembic upgrade head
```

## Create a New Migration

When ORM model changes have been made in `packages/kutana-core/src/kutana_core/database/models.py`:

1. **Ensure the latest code is deployed** (the api-server pod needs the updated models):
   - Push code, pull on DGX, build and deploy the api-server image
   - Or use the `/deploy` skill

2. **Auto-generate the migration inside the pod:**
   ```bash
   kubectl exec -n kutana deploy/api-server -- python -m alembic revision --autogenerate -m "description_of_changes"
   ```

3. **Copy the generated migration file back to local repo:**
   ```bash
   # Find the new migration file
   kubectl exec -n kutana deploy/api-server -- ls -t alembic/versions/ | head -1
   # Copy it out
   kubectl cp kutana/$(kubectl get pod -n kutana -l app=api-server -o jsonpath='{.items[0].metadata.name}'):alembic/versions/<filename>.py alembic/versions/<filename>.py
   ```

4. **Review the migration** — always check the generated `upgrade()` and `downgrade()` functions.

5. **Apply it:**
   ```bash
   kubectl exec -n kutana deploy/api-server -- python -m alembic upgrade head
   ```

## Write a Manual Migration

If autogenerate isn't suitable (data migrations, complex operations):

1. Create the file locally in `alembic/versions/` following the naming pattern: `<revision_id>_<description>.py`
2. Set `revision` to a unique ID and `down_revision` to the current head
3. Deploy, then apply as above

## Verify Columns

```bash
kubectl exec -n kutana deploy/api-server -- python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='TABLE_NAME' ORDER BY ordinal_position\"))
        for row in result:
            print(f'{row[0]:30s} {row[1]}')
    await engine.dispose()

asyncio.run(check())
"
```

Replace `TABLE_NAME` with the target table (e.g., `users`, `meetings`).

## Downgrade

```bash
# Downgrade one revision
kubectl exec -n kutana deploy/api-server -- python -m alembic downgrade -1

# Downgrade to specific revision
kubectl exec -n kutana deploy/api-server -- python -m alembic downgrade <revision_id>
```

## Troubleshooting

- **`ModuleNotFoundError: kutana_core`** — The api-server image doesn't have the latest code. Rebuild and redeploy.
- **Connection refused** — Don't run Alembic from the DGX host or locally. Always use `kubectl exec` into the api-server pod.
- **Migration conflicts** — If two migrations share the same `down_revision`, resolve by editing one to chain after the other.
