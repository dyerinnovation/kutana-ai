# Summary: Create `packages/convene-core/` Package

## Work Completed

- Created `packages/convene-core/pyproject.toml` with all required dependencies (pydantic, sqlalchemy[asyncio], asyncpg, pgvector, alembic)
- Created `packages/convene-core/src/convene_core/__init__.py` with package docstring
- Created 6 Pydantic v2 domain models in `models/`:
  - `meeting.py` - Meeting model with MeetingStatus enum, timezone-aware datetime validation, started_at <= ended_at validation
  - `participant.py` - Participant model with ParticipantRole enum (HOST, PARTICIPANT, AGENT)
  - `task.py` - Task model with TaskPriority/TaskStatus enums, VALID_TRANSITIONS dict, validate_transition classmethod
  - `decision.py` - Decision model with participants_present tracking
  - `transcript.py` - TranscriptSegment model with confidence range validation (0.0-1.0) and time ordering validation
  - `agent.py` - AgentConfig model with capabilities and meeting_type_filter lists
- Created `models/__init__.py` re-exporting all models and enums
- Created 6 event definitions in `events/definitions.py`:
  - BaseEvent with event_id, timestamp, to_dict() method
  - MeetingStarted, MeetingEnded, TranscriptSegmentFinal, TaskCreated, TaskUpdated, DecisionRecorded
  - Each with ClassVar event_type string
- Created `events/__init__.py` re-exporting all events
- Created 3 provider ABCs in `interfaces/`:
  - `stt.py` - STTProvider (start_stream, send_audio, get_transcript, close)
  - `tts.py` - TTSProvider (synthesize, get_voices) with Voice Pydantic model
  - `llm.py` - LLMProvider (extract_tasks, summarize, generate_report)
- Created `interfaces/__init__.py` re-exporting all interfaces
- Created database layer in `database/`:
  - `base.py` - SQLAlchemy DeclarativeBase
  - `models.py` - 6 ORM models (MeetingORM, ParticipantORM, TaskORM, DecisionORM, TranscriptSegmentORM, AgentConfigORM) with proper ForeignKeys, indexes, relationships
  - `session.py` - Async engine factory, session factory, get_session generator for DI
  - `__init__.py` re-exporting all database components
- Created test suite:
  - `tests/test_models.py` - 27 tests covering all models, validators, enums, serialization roundtrips, edge cases
  - `tests/test_events.py` - 14 tests covering all events, to_dict, nested serialization
- Created Alembic setup:
  - `alembic.ini` at repo root with async PostgreSQL URL
  - `alembic/env.py` with async migration pattern
  - `alembic/script.py.mako` standard migration template
  - `alembic/versions/.gitkeep` empty versions directory

## Work Remaining

- Run `uv sync` to install dependencies (requires shell permission)
- Run `pytest packages/convene-core/tests/` to verify all tests pass
- Run `ruff check` and `ruff format` to verify lint/format compliance
- Run `mypy packages/convene-core/` to verify type checking
- Generate initial Alembic migration with `alembic revision --autogenerate -m "initial"`
- Consider adding `conftest.py` with shared fixtures if test suite grows

## Lessons Learned

- All Python files use `from __future__ import annotations` for PEP 604 union syntax compatibility
- Pydantic v2 ClassVar fields are excluded from serialization by default, so `to_dict()` must manually add `event_type`
- SQLAlchemy 2.0 `Mapped[...]` + `mapped_column(...)` style requires explicit type annotations
- JSONB is preferred over ARRAY for list-of-UUID storage in PostgreSQL for flexibility
- The `sa.Date` column type should map to Python `date`, not `datetime`
- The database ORM models use `server_default=sa.func.now()` for timestamp defaults (DB-side) while Pydantic models use `default_factory=_utc_now` (Python-side)
