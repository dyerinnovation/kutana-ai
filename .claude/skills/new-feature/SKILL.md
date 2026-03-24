---
name: new-feature
description: Scaffold a new Convene AI feature following the ABC provider pattern. TRIGGER on: new feature, scaffold feature, create provider, add service, new extractor, new integration.
permissions:
  - Bash(uv:*)
---

# New Feature

Checklist and scaffold script for adding a new feature following Convene's ABC pattern.

## Checklist

- [ ] Define the ABC in `packages/convene-core/src/convene_core/interfaces/<name>.py`
- [ ] Add domain models to `packages/convene-core/src/convene_core/models/`
- [ ] Add event definitions to `packages/convene-core/src/convene_core/events.py`
- [ ] Implement the provider in `packages/convene-providers/src/convene_providers/<name>.py`
- [ ] Register in the provider registry
- [ ] Wire into the relevant service
- [ ] Add API endpoint(s) if user-facing
- [ ] Write tests alongside each file
- [ ] Update `docs/TASKLIST.md` and relevant `docs/technical/` pages
- [ ] Update `CLAUDE.md` if this changes how future Claude sessions work

## Scaffold

```bash
bash .claude/skills/new-feature/scripts/scaffold-feature.sh <feature-name>
```

Creates the interface, stub implementation, and test files. See `claude_docs/Convene_Core_Patterns.md` and `claude_docs/Provider_Patterns.md`.
