# Documentation Rules

Update docs **alongside** the feature code — never as a separate follow-up commit.

For any new feature or changed behavior, update:
- `README.md` — project root and affected package/service READMEs
- `internal-docs/development/TASKLIST.md` — mark items complete, update phase if needed
- `internal-docs/` — internal strategy, roadmap, cost, architecture decisions, patterns
- `external-docs/` — user-facing features, API auth, integrations, getting started
- `internal-docs/architecture/patterns/` — update or add a pattern doc if the pattern is new

API changes require docstrings, OpenAPI descriptions, and an `external-docs/` page.

When updating phase numbering, update all three: `internal-docs/development/TASKLIST.md`, `CLAUDE.md`, `external-docs/README.md`.
