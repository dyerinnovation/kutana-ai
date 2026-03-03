# Plan: Create `packages/convene-core/` Package

## Objective
Create the full `convene-core` package for the Convene AI monorepo. This package contains domain models (Pydantic v2), event definitions, provider ABCs (interfaces), database layer (SQLAlchemy 2.0 async), tests, and Alembic migration setup.

## Requirements
- Python 3.12+, strict type hints, `from __future__ import annotations` in every file
- Pydantic v2 models with validators
- SQLAlchemy 2.0 async style with `mapped_column`
- Google-style docstrings
- 100 char line length limit
- All tests designed to pass

## Files to Create

### Package setup
1. `packages/convene-core/pyproject.toml`

### Domain Models (Pydantic v2)
2. `packages/convene-core/src/convene_core/__init__.py`
3. `packages/convene-core/src/convene_core/models/__init__.py`
4. `packages/convene-core/src/convene_core/models/meeting.py`
5. `packages/convene-core/src/convene_core/models/participant.py`
6. `packages/convene-core/src/convene_core/models/task.py`
7. `packages/convene-core/src/convene_core/models/decision.py`
8. `packages/convene-core/src/convene_core/models/transcript.py`
9. `packages/convene-core/src/convene_core/models/agent.py`

### Events
10. `packages/convene-core/src/convene_core/events/__init__.py`
11. `packages/convene-core/src/convene_core/events/definitions.py`

### Provider Interfaces (ABCs)
12. `packages/convene-core/src/convene_core/interfaces/__init__.py`
13. `packages/convene-core/src/convene_core/interfaces/stt.py`
14. `packages/convene-core/src/convene_core/interfaces/tts.py`
15. `packages/convene-core/src/convene_core/interfaces/llm.py`

### Database Layer
16. `packages/convene-core/src/convene_core/database/__init__.py`
17. `packages/convene-core/src/convene_core/database/base.py`
18. `packages/convene-core/src/convene_core/database/models.py`
19. `packages/convene-core/src/convene_core/database/session.py`

### Tests
20. `packages/convene-core/tests/__init__.py`
21. `packages/convene-core/tests/test_models.py`
22. `packages/convene-core/tests/test_events.py`

### Alembic Setup (repo root)
23. `alembic.ini`
24. `alembic/env.py`
25. `alembic/script.py.mako`
26. `alembic/versions/.gitkeep`

## Approach
- Create all directory structures first
- Write each file with complete, working code
- Ensure all imports are correct and cross-reference properly
- Run tests at the end to verify
