# Summary: Create `packages/convene-providers/` and `packages/convene-memory/`

## Work Completed

### convene-providers (12 files)
- `pyproject.toml` -- package config with httpx, websockets, anthropic deps and optional extras
- `src/convene_providers/__init__.py` -- package docstring
- `src/convene_providers/stt/__init__.py` -- re-exports AssemblyAISTT and DeepgramSTT
- `src/convene_providers/stt/assemblyai_stt.py` -- Full AssemblyAI real-time WebSocket STT with base64 audio, session management, and FinalTranscript yielding
- `src/convene_providers/stt/deepgram_stt.py` -- Full Deepgram WebSocket STT with Nova-2, raw byte audio, diarization, and is_final filtering
- `src/convene_providers/tts/__init__.py` -- re-exports CartesiaTTS and ElevenLabsTTS
- `src/convene_providers/tts/cartesia_tts.py` -- Cartesia HTTP streaming TTS with PCM output and voice listing
- `src/convene_providers/tts/elevenlabs_tts.py` -- ElevenLabs HTTP streaming TTS with MP3 output and voice listing
- `src/convene_providers/llm/__init__.py` -- re-exports AnthropicLLM
- `src/convene_providers/llm/anthropic_llm.py` -- Full Anthropic Claude LLM with tool_use-based task extraction, summarization, and report generation
- `src/convene_providers/registry.py` -- ProviderType enum, ProviderRegistry factory class, default_registry singleton with all 5 providers pre-registered
- `tests/__init__.py` -- empty test package

### convene-memory (7 files)
- `pyproject.toml` -- package config with redis, sqlalchemy, asyncpg, pgvector deps
- `src/convene_memory/__init__.py` -- package docstring
- `src/convene_memory/working.py` -- Redis hash-backed working memory per active meeting (store/retrieve/get_all/clear)
- `src/convene_memory/short_term.py` -- SQLAlchemy async queries for recent meetings by participant and tasks by meeting, with ORM read models
- `src/convene_memory/long_term.py` -- pgvector-backed semantic search with MeetingSummaryEmbedding ORM model (Vector(1536)), cosine distance search
- `src/convene_memory/structured.py` -- Indexed task/decision queries returning domain models, with dependency traversal
- `tests/__init__.py` -- empty test package

## Work Remaining
- Write unit tests for each provider (mock WebSocket, httpx, and Anthropic client)
- Write integration tests for memory layers (requires test database fixtures)
- Add database migration (Alembic) for `meeting_summary_embeddings`, `meeting_participants` tables
- Wire up the memory layers into a unified `MemoryContext` builder
- Add health-check / ping methods to each provider

## Lessons Learned
- The convene-core package was already created by a prior session with full models, interfaces, and events. Always check existing files before creating dependencies.
- `convene_core.interfaces.stt.STTProvider.get_transcript()` is defined with `def get_transcript(self) -> AsyncIterator[...]` (not `async def`) in the core ABC, since async generators use `async def` in the implementation but the ABC signature is just `def` returning `AsyncIterator`.
- The core `Task` model uses `date` (not `datetime`) for `due_date`, and `decided_by_id` (not `decided_by`) for the Decision model -- these field names must match exactly in ORM-to-model conversions.
- The `websockets` library v13+ uses `websockets.asyncio.client.ClientConnection` as the type for async WebSocket connections.
- Redis asyncio imports use `redis.asyncio as aioredis` pattern per redis-py 5.x conventions.
