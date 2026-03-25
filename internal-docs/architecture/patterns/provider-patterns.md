# Provider Implementation Patterns

## ABC Signatures
- `STTProvider.get_transcript()` uses `def` (not `async def`) returning `AsyncIterator[TranscriptSegment]` in the ABC. Implementations use `async def` since they are async generators.
- `TTSProvider.synthesize()` follows the same pattern -- `def` in ABC, `async def` in implementation.
- `LLMProvider` methods are all `async def` in the ABC.

## Core Model Field Names
- `Task.due_date` is `date` (not `datetime`)
- `Decision.decided_by_id` (not `decided_by`)
- `Task.validate_transition()` is a classmethod, not instance method

## Third-Party Library Conventions
- `websockets` v13+: use `websockets.asyncio.client.ClientConnection` for type hints
- `redis-py` 5.x: use `import redis.asyncio as aioredis` pattern
- `anthropic`: use `anthropic.AsyncAnthropic` for async client
- `httpx`: use `httpx.AsyncClient` with `stream()` context manager for streaming responses
- `pgvector`: use `pgvector.sqlalchemy.Vector` column type with `cosine_distance()` for similarity search

## Provider Registry
- Located at `packages/convene-providers/src/convene_providers/registry.py`
- `default_registry` singleton has all built-in providers pre-registered
- Use lazy imports inside `_build_default_registry()` to avoid circular imports
