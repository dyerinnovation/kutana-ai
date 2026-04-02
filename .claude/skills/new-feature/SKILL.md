---
name: new-feature
description: Scaffold a new Kutana AI feature following the ABC provider pattern. TRIGGER on: new feature, scaffold feature, create provider, add service, new extractor, new integration.
permissions:
  - Bash(uv:*)
---

# New Feature

Checklist and scaffold script for adding a new feature following Kutana's ABC pattern.

## Checklist

- [ ] Define the ABC in `packages/kutana-core/src/kutana_core/interfaces/<name>.py`
- [ ] Add domain models to `packages/kutana-core/src/kutana_core/models/`
- [ ] Add event definitions to `packages/kutana-core/src/kutana_core/events.py`
- [ ] Implement the provider in `packages/kutana-providers/src/kutana_providers/<name>.py`
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

Creates the interface, stub implementation, and test files. See `claude_docs/Kutana_Core_Patterns.md` and `claude_docs/Provider_Patterns.md`.
