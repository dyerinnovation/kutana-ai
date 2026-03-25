# Documentation Rules

Update docs **alongside** the feature code — never as a separate follow-up commit.

For any new feature or changed behavior, update:
- `README.md` — project root and affected package/service READMEs
- `docs/TASKLIST.md` — mark items complete, update phase if needed
- `docs/technical/` or `docs/integrations/` — add/update the relevant page
- `claude_docs/` — update or add a reference doc if the pattern is new

API changes require docstrings, OpenAPI descriptions, and a `docs/technical/` page.

When updating phase numbering, update all three: `docs/TASKLIST.md`, `CLAUDE.md`, `docs/README.md`.
