# Convene Core Package Patterns

## Package Structure

```
packages/convene-core/
├── pyproject.toml
├── src/convene_core/
│   ├── __init__.py
│   ├── models/          # Pydantic v2 domain models
│   ├── events/          # Event definitions for inter-service communication
│   ├── interfaces/      # Abstract base classes for providers
│   └── database/        # SQLAlchemy 2.0 ORM models + session management
└── tests/
```

## Key Patterns

### Pydantic Models
- All files start with `from __future__ import annotations`
- Use `Field(default_factory=...)` for mutable defaults (lists, UUIDs, datetimes)
- Use `model_validator(mode="after")` for cross-field validation
- Helper function `_utc_now()` returns `datetime.now(tz=timezone.utc)` for timestamp defaults
- All datetimes must be timezone-aware (validated in model_validator)

### Enums
- All enums inherit from `(str, enum.Enum)` for JSON-friendly serialization
- Values are lowercase strings (e.g., `PENDING = "pending"`)

### Task Status Transitions
- `VALID_TRANSITIONS` dict maps each `TaskStatus` to a set of valid target statuses
- `Task.validate_transition(from_status, to_status) -> bool` classmethod checks validity
- `DONE` is terminal (no outgoing transitions)

### Events
- `BaseEvent` has `event_id: UUID`, `event_type: ClassVar[str]`, `timestamp: datetime`
- `to_dict()` returns `model_dump(mode="json")` with `event_type` manually added (ClassVar excluded from serialization)
- Event naming: `"meeting.started"`, `"task.created"`, `"transcript.segment.final"`

### Database ORM
- Uses `Mapped[...]` + `mapped_column(...)` SQLAlchemy 2.0 style
- UUID PKs with `sa.Uuid` column type and `default=uuid4`
- Timestamps use `server_default=sa.func.now()` (DB-side defaults)
- JSONB for list-of-UUID fields (dependencies, participants_present, capabilities)
- Indexes on foreign key columns and status columns

### Session Management
- `create_engine(url)` wraps `create_async_engine`
- `create_session_factory(engine)` returns `async_sessionmaker`
- `get_session(factory)` is an async generator for FastAPI dependency injection with auto commit/rollback

### Provider Interfaces
- Pure ABCs with `@abstractmethod` decorators
- Use `AsyncIterator` for streaming (STT transcripts, TTS audio)
- No implementation details in the interface
