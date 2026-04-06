# Database Migration Rules

## Coordination Across Agents

Alembic migrations form a linear chain — every migration has exactly one parent (`down_revision`). When multiple agents work in parallel (worktrees, CoWork sessions, or teams), migrations **must be coordinated** to avoid branching the chain.

### How to Coordinate

1. **Designate a migration coordinator.** When a team of agents is working in parallel, one agent owns migration creation. Other agents that need schema changes communicate their requirements (table name, columns, constraints, indexes) to the coordinator, who creates all migrations in the correct sequence.

2. **Never create migrations independently in parallel worktrees.** Two migrations pointing to the same `down_revision` will break the deploy pipeline. If you need a schema change, tell the coordinating agent what you need instead of creating your own migration file.

3. **Merge order matters.** If migrations were created in separate branches despite this rule, they must be merged one at a time. After each merge, update the next migration's `down_revision` to point to the one just merged. Verify with: `grep -r "down_revision" alembic/versions/` — no two files should share the same value.

### Before Creating a Migration

- Read the latest migration in `alembic/versions/` and set `down_revision` to its revision ID.
- Confirm no other agent is currently creating a migration (check with your team).

### Helm Migration Job

The Helm chart runs `alembic upgrade head` as a post-upgrade hook. If this job fails:
1. Check if tables already exist (e.g., manual apply via psql).
2. Stamp `alembic_version` to the correct head revision.
3. Delete the failed job: `kubectl delete job kutana-migrate -n kutana`.
4. Re-run `helm upgrade`.
