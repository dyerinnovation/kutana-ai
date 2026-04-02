# Phase B: Meeting Insight Stream — Completion Summary

## Work Completed

- **Entity schema** (`kutana_core/extraction/types.py`): 7 Pydantic v2 entity models
  (`TaskEntity`, `DecisionEntity`, `QuestionEntity`, `EntityMentionEntity`, `KeyPointEntity`,
  `BlockerEntity`, `FollowUpEntity`) all inheriting from `ExtractedEntity` base with auto-UUID
  `id`, `entity_type` discriminator, `meeting_id`, `confidence`, `extracted_at`, `batch_id`,
  and `content_key()` method. `AnyExtractedEntity` discriminated union for serialization.
  `TranscriptBatch` and `ExtractionResult` containers also defined.

- **Extractor ABC** (`kutana_core/extraction/abc.py`): Abstract `Extractor` with
  `extract(batch) -> ExtractionResult`, `name: str` property, `entity_types: list[str]` property.

- **BatchCollector** (`kutana_core/extraction/collector.py`): Subscribes to
  `meeting.{id}.transcript`, buffers `BatchSegment` objects in a rolling window,
  asyncio background flush loop (1s tick), triggers extractors on window expiry,
  publishes to `meeting.{id}.insights` (full) and `meeting.{id}.insights.{type}` (per-type).
  Final flush on `stop()`.

- **EntityDeduplicator** (`kutana_core/extraction/deduplicator.py`): Per-meeting registry,
  `process()` / `get_all()` / `clear()` API. `difflib.SequenceMatcher` similarity (0.85
  threshold), min-confidence filter (0.3), merge keeps higher-confidence entity.

- **LLMExtractor** (`kutana_providers/extraction/llm_extractor.py`): Implements `Extractor`
  ABC using `anthropic.AsyncAnthropic` with `extract_meeting_entities` tool-use schema covering
  all 7 types. Parses response via `model_validate` per entity type. `# type: ignore[call-overload]`
  on the Anthropic `messages.create()` call (same pattern as existing providers).

- **Registry** (`kutana_providers/registry.py`): Added `ProviderType.EXTRACTOR = "extractor"`,
  registered `LLMExtractor` as `"llm"` in `_build_default_registry()`.

- **Tests**: 75 tests, all passing. Coverage: entity model validation, discriminated union
  roundtrip, Extractor ABC contract, BatchCollector subscribe/flush/publish/stop, EntityDeduplicator
  dedup/merge/filter/isolation, LLMExtractor mocked Anthropic responses (all 7 types + mixed +
  invalid + no-tool-block), registry integration.

## Work Remaining

- No remaining work for this phase.
- Potential future enhancements:
  - Wire `BatchCollector` + `EntityDeduplicator` into the `task-engine` service
  - Persist `ExtractedEntity` objects to PostgreSQL (ORM models + alembic migration)
  - Add Redis-backed `EntityDeduplicator` for cross-process deduplication
  - Add `LLMExtractor` confidence calibration (the model's output confidence vs extractor confidence)
  - Implement `EntityMentionEntity` entity resolution (merge mentions of the same person/system)

## Lessons Learned

- `AnyExtractedEntity: TypeAlias` vs `type AnyExtractedEntity =` — ruff UP007 enforces
  the `X | Y` pipe syntax for union types; `Annotated[X | Y | Z, Field(discriminator=...)]`
  works correctly with Pydantic v2 and Python 3.12 discriminated unions.

- `Subscription` from `kutana_core.messaging.types` should be in `TYPE_CHECKING` block
  (ruff TC001) since `from __future__ import annotations` makes all annotations lazy strings
  — no runtime import needed.

- Anthropic `messages.create()` overloads don't accept `dict[str, Any]` for `tools` —
  use `# type: ignore[call-overload]` on the first line of the call (not on the `tools=` line).
  CI only runs mypy on `packages/kutana-core/` so providers files don't get checked.

- `difflib.SequenceMatcher` is ideal for entity deduplication — no dependencies, works well
  for natural language strings, and the ratio in [0, 1] maps naturally to a threshold.

- Pydantic's `model_validate` is the correct way to parse LLM JSON responses into typed entities —
  it validates enum values, required fields, and ranges, and raises `ValidationError` for
  malformed entries which can be caught and logged without crashing the pipeline.
