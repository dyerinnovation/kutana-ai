# Phase B: Meeting Insight Stream — Entity Schema & Extraction Pipeline

## Objective
Implement the Meeting Insight Stream extraction pipeline for Convene AI. This adds a structured
entity extraction layer that consumes windowed transcript batches, extracts 7 entity types via
an LLM, deduplicates results, and publishes insights to the message bus.

## Files to Create

### convene-core: extraction module
- `packages/convene-core/src/convene_core/extraction/__init__.py`
- `packages/convene-core/src/convene_core/extraction/types.py` — entity schema + batch types
- `packages/convene-core/src/convene_core/extraction/abc.py` — Extractor ABC
- `packages/convene-core/src/convene_core/extraction/collector.py` — BatchCollector service
- `packages/convene-core/src/convene_core/extraction/deduplicator.py` — EntityDeduplicator

### convene-providers: LLM extractor
- `packages/convene-providers/src/convene_providers/extraction/__init__.py`
- `packages/convene-providers/src/convene_providers/extraction/llm_extractor.py`

### Tests
- `packages/convene-core/tests/test_extraction.py`
- `packages/convene-providers/tests/test_llm_extractor.py`

## Files to Modify
- `packages/convene-providers/src/convene_providers/registry.py` — add ProviderType.EXTRACTOR,
  register LLMExtractor as "llm"

## Entity Types (7 total)

All inherit from `ExtractedEntity` base:
- `id` — auto UUID string
- `entity_type` — discriminator (Pydantic v2 discriminated union)
- `meeting_id` — string
- `confidence` — float 0-1, default 0.85
- `extracted_at` — UTC datetime
- `batch_id` — string (which extraction batch produced this)
- `content_key()` — method returning primary content for deduplication

### 1. TaskEntity (`entity_type="task"`)
- `title: str`
- `assignee: str | None`
- `deadline: str | None`
- `priority: Literal["high", "medium", "low"]` default "medium"
- `status: Literal["identified", "accepted", "completed"]` default "identified"
- `source_speaker: str | None`
- `source_segment_id: str | None`
- `content_key()` → title.lower()

### 2. DecisionEntity (`entity_type="decision"`)
- `summary: str`
- `participants: list[str]`
- `rationale: str` default ""
- `source_segment_ids: list[str]`
- `content_key()` → summary.lower()

### 3. QuestionEntity (`entity_type="question"`)
- `text: str`
- `asker: str | None`
- `status: Literal["open", "answered"]` default "open"
- `answer: str | None`
- `source_segment_id: str | None`
- `content_key()` → text.lower()

### 4. EntityMentionEntity (`entity_type="entity_mention"`)
- `name: str`
- `kind: Literal["person", "system", "concept", "org"]` (renamed from entity_type to avoid clash)
- `context: str` default ""
- `first_mention_segment_id: str | None`
- `content_key()` → f"{name.lower()}:{kind}"

### 5. KeyPointEntity (`entity_type="key_point"`)
- `summary: str`
- `speaker: str | None`
- `topic: str` default ""
- `importance: Literal["high", "medium", "low"]` default "medium"
- `source_segment_id: str | None`
- `content_key()` → summary.lower()

### 6. BlockerEntity (`entity_type="blocker"`)
- `description: str`
- `owner: str | None`
- `severity: Literal["critical", "high", "medium", "low"]` default "medium"
- `related_tasks: list[str]`
- `source_segment_id: str | None`
- `content_key()` → description.lower()

### 7. FollowUpEntity (`entity_type="follow_up"`)
- `description: str`
- `owner: str | None`
- `due_context: str | None`
- `source_segment_id: str | None`
- `content_key()` → description.lower()

## Batch / Result Types

### BatchSegment
- `segment_id: str`
- `speaker: str | None`
- `text: str`
- `start_time: float`
- `end_time: float`

### TranscriptBatch
- `batch_id: str` (auto UUID)
- `meeting_id: str`
- `segments: list[BatchSegment]`
- `context_segments: list[BatchSegment]` (previous batch for continuity)
- `batch_window_seconds: float` default 30.0

### ExtractionResult
- `batch_id: str`
- `entities: list[AnyExtractedEntity]` (discriminated union)
- `processing_time_ms: float`

## Extractor ABC (convene-core)
```python
class Extractor(ABC):
    async def extract(batch: TranscriptBatch) -> ExtractionResult: ...
    @property name(self) -> str: ...
    @property entity_types(self) -> list[str]: ...
```

## BatchCollector (convene-core)
- Subscribes to `meeting.{meeting_id}.transcript`
- Buffers `BatchSegment` objects in a rolling window
- asyncio background task flushes every 1s; fires when `elapsed >= batch_window_seconds`
- Passes `TranscriptBatch` to all registered extractors sequentially
- Publishes `ExtractionResult` to:
  - `meeting.{meeting_id}.insights` (full result)
  - `meeting.{meeting_id}.insights.{entity_type}` (per type)

## EntityDeduplicator (convene-core)
- `process(meeting_id, new_entities) -> list[AnyExtractedEntity]` (returns unique new entities)
- `get_all(meeting_id) -> list[AnyExtractedEntity]` (all deduplicated entities for meeting)
- Similarity: `difflib.SequenceMatcher` ratio, threshold 0.85
- Low-confidence filter: entities with confidence < 0.3 discarded
- Merge: higher-confidence entity wins; `model_copy(update={...})`

## LLMExtractor (convene-providers)
- Implements `Extractor` ABC
- Uses `anthropic.AsyncAnthropic` (same pattern as `AnthropicLLM`)
- Tool-use schema covers all 7 entity types
- Parses response via `model_validate` on each entity dict (merges meeting_id, batch_id)
- `name = "llm-extractor"`, `entity_types = [all 7]`
- Constructor: `api_key: str`, `model: str = "claude-sonnet-4-20250514"`

## Registry
- Add `ProviderType.EXTRACTOR = "extractor"` to StrEnum
- Register `LLMExtractor` as `"llm"` in `_build_default_registry()`

## Recovery Notes
- Project root: `/Users/jonathandyer/Documents/Dyer_Innovation/dev/convene-ai`
- Python 3.12+, mypy strict, ruff formatting, pytest asyncio_mode=auto
- MessageBus pattern: `MockMessageBus` in `convene_providers.testing`
- Pydantic v2 discriminated union: `Annotated[Union[...], Field(discriminator="entity_type")]`
- All tests use `--import-mode=importlib` (set in root pyproject.toml)
- Commit: `feat: add Meeting Insight Stream entity schema, extraction pipeline, and batch collector`
- Co-Author: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
