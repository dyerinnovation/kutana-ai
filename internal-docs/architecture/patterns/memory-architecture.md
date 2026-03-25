# Memory Architecture

## Four-Layer System

### Working Memory (Redis)
- `packages/convene-memory/src/convene_memory/working.py`
- Redis hash per active meeting (`convene:working:{meeting_id}`)
- Ephemeral -- cleared when meeting ends
- Methods: `store()`, `retrieve()`, `get_all()`, `clear()`

### Short-Term Memory (PostgreSQL)
- `packages/convene-memory/src/convene_memory/short_term.py`
- SQLAlchemy async queries against `meetings`, `meeting_participants`, `tasks` tables
- ORM read models (not the authoritative write models)
- Methods: `get_recent_meetings()`, `get_recent_tasks()`

### Long-Term Memory (pgvector)
- `packages/convene-memory/src/convene_memory/long_term.py`
- `MeetingSummaryEmbedding` ORM model with `Vector(1536)` column
- Cosine distance for semantic similarity search
- Methods: `store_embedding()`, `search_similar()`

### Structured Memory (PostgreSQL)
- `packages/convene-memory/src/convene_memory/structured.py`
- Indexed queries on `tasks` and `decisions` tables
- Returns domain model instances (Task, Decision) not ORM rows
- Methods: `get_open_tasks()`, `get_decisions()`, `get_task_dependencies()`

## ORM-to-Domain Conversion
- Each memory layer defines its own ORM models with `_Base(DeclarativeBase)`
- Private converter functions (`_task_row_to_model`, `_decision_row_to_model`) handle ORM-to-Pydantic mapping
- Dependencies stored as `ARRAY(String)` in PostgreSQL, converted to `list[UUID]` in domain models
