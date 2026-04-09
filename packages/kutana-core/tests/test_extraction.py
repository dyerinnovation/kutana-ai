"""Tests for the Meeting Insight Stream extraction pipeline (kutana-core)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from kutana_core.extraction.abc import Extractor
from kutana_core.extraction.collector import BatchCollector
from kutana_core.extraction.deduplicator import EntityDeduplicator, _similarity
from kutana_core.extraction.types import (
    AnyExtractedEntity,
    BatchSegment,
    BlockerEntity,
    DecisionEntity,
    EntityMentionEntity,
    ExtractedEntity,
    ExtractionResult,
    FollowUpEntity,
    KeyPointEntity,
    QuestionEntity,
    TaskEntity,
    TranscriptBatch,
)
from kutana_providers.testing import MockMessageBus  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MEETING_ID = str(uuid4())
BATCH_ID = str(uuid4())


def _make_task(**kwargs: object) -> TaskEntity:
    """Create a TaskEntity with sensible defaults."""
    return TaskEntity(
        meeting_id=MEETING_ID,
        batch_id=BATCH_ID,
        title=str(kwargs.pop("title", "Fix the login bug")),
        **kwargs,
    )


def _make_decision(**kwargs: object) -> DecisionEntity:
    return DecisionEntity(
        meeting_id=MEETING_ID,
        batch_id=BATCH_ID,
        summary=str(kwargs.pop("summary", "Use PostgreSQL for storage")),
        **kwargs,
    )


def _make_batch(n_segments: int = 3) -> TranscriptBatch:
    segments = [
        BatchSegment(
            segment_id=str(uuid4()),
            speaker=f"spk_{i}",
            text=f"Segment text {i}.",
            start_time=float(i * 10),
            end_time=float(i * 10 + 5),
        )
        for i in range(n_segments)
    ]
    return TranscriptBatch(
        meeting_id=MEETING_ID,
        segments=segments,
    )


# ---------------------------------------------------------------------------
# Entity model tests
# ---------------------------------------------------------------------------


class TestTaskEntity:
    def test_create_with_defaults(self) -> None:
        task = _make_task()
        assert task.entity_type == "task"
        assert task.priority == "medium"
        assert task.status == "identified"
        assert isinstance(task.id, str) and len(task.id) == 36
        assert task.confidence == pytest.approx(0.85)

    def test_create_with_all_fields(self) -> None:
        task = TaskEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            title="Deploy to staging",
            assignee="Alice",
            deadline="2026-04-01",
            priority="high",
            status="accepted",
            source_speaker="Bob",
            source_segment_id="seg_001",
            confidence=0.95,
        )
        assert task.assignee == "Alice"
        assert task.priority == "high"
        assert task.status == "accepted"
        assert task.confidence == pytest.approx(0.95)

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValidationError):
            TaskEntity(
                meeting_id=MEETING_ID,
                batch_id=BATCH_ID,
                title="Some task",
                priority="urgent",
            )

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            TaskEntity(
                meeting_id=MEETING_ID,
                batch_id=BATCH_ID,
                title="Bad confidence",
                confidence=1.5,
            )

    def test_content_key(self) -> None:
        task = _make_task(title="  Fix Login Bug  ")
        assert task.content_key() == "fix login bug"

    def test_serialization_roundtrip(self) -> None:
        task = _make_task()
        data = task.model_dump(mode="json")
        restored = TaskEntity.model_validate(data)
        assert restored.id == task.id
        assert restored.title == task.title
        assert restored.entity_type == "task"


class TestDecisionEntity:
    def test_create_with_defaults(self) -> None:
        d = _make_decision()
        assert d.entity_type == "decision"
        assert d.participants == []
        assert d.rationale == ""

    def test_content_key(self) -> None:
        d = _make_decision(summary="  Use Python  ")
        assert d.content_key() == "use python"

    def test_serialization_roundtrip(self) -> None:
        d = _make_decision(participants=["Alice", "Bob"])
        data = d.model_dump(mode="json")
        restored = DecisionEntity.model_validate(data)
        assert restored.participants == ["Alice", "Bob"]


class TestQuestionEntity:
    def test_create_defaults(self) -> None:
        q = QuestionEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            text="When is the release date?",
        )
        assert q.entity_type == "question"
        assert q.status == "open"
        assert q.answer is None

    def test_answered_question(self) -> None:
        q = QuestionEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            text="Is the API ready?",
            status="answered",
            answer="Yes, it was deployed yesterday.",
        )
        assert q.status == "answered"
        assert q.answer is not None

    def test_content_key(self) -> None:
        q = QuestionEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            text="  What is the deadline?  ",
        )
        assert q.content_key() == "what is the deadline?"


class TestEntityMentionEntity:
    def test_create(self) -> None:
        e = EntityMentionEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            name="Stripe",
            kind="system",
        )
        assert e.entity_type == "entity_mention"
        assert e.kind == "system"

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValidationError):
            EntityMentionEntity(
                meeting_id=MEETING_ID,
                batch_id=BATCH_ID,
                name="Foo",
                kind="software",
            )

    def test_content_key(self) -> None:
        e = EntityMentionEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            name="  AWS  ",
            kind="system",
        )
        assert e.content_key() == "aws:system"


class TestKeyPointEntity:
    def test_create_defaults(self) -> None:
        k = KeyPointEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            summary="We need to refactor the auth module.",
        )
        assert k.entity_type == "key_point"
        assert k.importance == "medium"

    def test_content_key(self) -> None:
        k = KeyPointEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            summary="  Refactor the module  ",
        )
        assert k.content_key() == "refactor the module"


class TestBlockerEntity:
    def test_create_defaults(self) -> None:
        b = BlockerEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            description="Waiting for API keys from vendor.",
        )
        assert b.entity_type == "blocker"
        assert b.severity == "medium"
        assert b.related_tasks == []

    def test_content_key(self) -> None:
        b = BlockerEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            description="  Missing credentials  ",
        )
        assert b.content_key() == "missing credentials"


class TestFollowUpEntity:
    def test_create_defaults(self) -> None:
        f = FollowUpEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            description="Send the design mockups to the team.",
        )
        assert f.entity_type == "follow_up"
        assert f.owner is None
        assert f.due_context is None

    def test_content_key(self) -> None:
        f = FollowUpEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            description="  Send mockups  ",
        )
        assert f.content_key() == "send mockups"


# ---------------------------------------------------------------------------
# Discriminated union tests
# ---------------------------------------------------------------------------


class TestDiscriminatedUnion:
    """Pydantic v2 discriminated union validation and serialization."""

    def test_validates_task_from_dict(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[AnyExtractedEntity] = TypeAdapter(AnyExtractedEntity)
        data = {
            "entity_type": "task",
            "meeting_id": MEETING_ID,
            "batch_id": BATCH_ID,
            "title": "Write unit tests",
        }
        entity = adapter.validate_python(data)
        assert isinstance(entity, TaskEntity)
        assert entity.title == "Write unit tests"

    def test_validates_decision_from_dict(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[AnyExtractedEntity] = TypeAdapter(AnyExtractedEntity)
        data = {
            "entity_type": "decision",
            "meeting_id": MEETING_ID,
            "batch_id": BATCH_ID,
            "summary": "Go with Option A",
        }
        entity = adapter.validate_python(data)
        assert isinstance(entity, DecisionEntity)

    def test_invalid_discriminator_raises(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[AnyExtractedEntity] = TypeAdapter(AnyExtractedEntity)
        with pytest.raises(ValidationError):
            adapter.validate_python(
                {
                    "entity_type": "unknown_type",
                    "meeting_id": MEETING_ID,
                    "batch_id": BATCH_ID,
                }
            )

    def test_all_entity_types_roundtrip(self) -> None:
        """All entity types can be serialized to JSON and re-validated."""
        from pydantic import TypeAdapter

        adapter: TypeAdapter[AnyExtractedEntity] = TypeAdapter(AnyExtractedEntity)

        entities: list[AnyExtractedEntity] = [
            _make_task(),
            _make_decision(),
            QuestionEntity(meeting_id=MEETING_ID, batch_id=BATCH_ID, text="Why?"),
            EntityMentionEntity(
                meeting_id=MEETING_ID, batch_id=BATCH_ID, name="Redis", kind="system"
            ),
            KeyPointEntity(meeting_id=MEETING_ID, batch_id=BATCH_ID, summary="Key insight."),
            BlockerEntity(meeting_id=MEETING_ID, batch_id=BATCH_ID, description="Blocked."),
            FollowUpEntity(meeting_id=MEETING_ID, batch_id=BATCH_ID, description="Follow up."),
        ]
        for entity in entities:
            data = entity.model_dump(mode="json")
            restored = adapter.validate_python(data)
            assert restored.entity_type == entity.entity_type
            assert restored.id == entity.id


# ---------------------------------------------------------------------------
# ExtractedEntity base class
# ---------------------------------------------------------------------------


class TestExtractedEntityBase:
    def test_extracted_at_is_utc(self) -> None:
        task = _make_task()
        assert task.extracted_at.tzinfo is not None

    def test_id_is_uuid_string(self) -> None:
        task = _make_task()
        assert len(task.id) == 36
        assert task.id.count("-") == 4

    def test_base_content_key_returns_empty(self) -> None:
        # Base class default returns ""
        base = ExtractedEntity(
            entity_type="task",
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
        )
        assert base.content_key() == ""


# ---------------------------------------------------------------------------
# TranscriptBatch and ExtractionResult
# ---------------------------------------------------------------------------


class TestTranscriptBatch:
    def test_create_with_segments(self) -> None:
        batch = _make_batch(3)
        assert len(batch.segments) == 3
        assert batch.context_segments == []
        assert batch.batch_window_seconds == 30.0

    def test_batch_id_auto_generated(self) -> None:
        b1 = _make_batch()
        b2 = _make_batch()
        assert b1.batch_id != b2.batch_id

    def test_with_context_segments(self) -> None:
        ctx = [
            BatchSegment(
                segment_id="prev_seg",
                speaker="Alice",
                text="Previous context.",
                start_time=0.0,
                end_time=2.0,
            )
        ]
        batch = TranscriptBatch(
            meeting_id=MEETING_ID,
            segments=[],
            context_segments=ctx,
        )
        assert len(batch.context_segments) == 1


class TestExtractionResult:
    def test_create_empty(self) -> None:
        result = ExtractionResult(
            batch_id=BATCH_ID,
            entities=[],
            processing_time_ms=42.5,
        )
        assert result.entities == []
        assert result.processing_time_ms == pytest.approx(42.5)

    def test_create_with_entities(self) -> None:
        result = ExtractionResult(
            batch_id=BATCH_ID,
            entities=[_make_task(), _make_decision()],
            processing_time_ms=120.0,
        )
        assert len(result.entities) == 2

    def test_serialization_roundtrip(self) -> None:
        result = ExtractionResult(
            batch_id=BATCH_ID,
            entities=[_make_task()],
            processing_time_ms=55.0,
        )
        data = result.model_dump(mode="json")
        restored = ExtractionResult.model_validate(data)
        assert len(restored.entities) == 1
        assert restored.entities[0].entity_type == "task"


# ---------------------------------------------------------------------------
# Extractor ABC contract
# ---------------------------------------------------------------------------


class TestExtractorABC:
    def test_concrete_extractor_satisfies_contract(self) -> None:
        """A concrete Extractor can be instantiated and called."""

        class AlwaysEmptyExtractor(Extractor):
            @property
            def name(self) -> str:
                return "empty"

            @property
            def entity_types(self) -> list[str]:
                return ["task"]

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                return ExtractionResult(
                    batch_id=batch.batch_id,
                    entities=[],
                    processing_time_ms=0.0,
                )

        extractor = AlwaysEmptyExtractor()
        assert extractor.name == "empty"
        assert extractor.entity_types == ["task"]

    async def test_extract_called_with_batch(self) -> None:
        """extract() is awaitable and returns an ExtractionResult."""

        class EchoExtractor(Extractor):
            @property
            def name(self) -> str:
                return "echo"

            @property
            def entity_types(self) -> list[str]:
                return ["task"]

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                # Return one task per segment
                entities: list[AnyExtractedEntity] = [
                    TaskEntity(
                        meeting_id=batch.meeting_id,
                        batch_id=batch.batch_id,
                        title=seg.text,
                    )
                    for seg in batch.segments
                ]
                return ExtractionResult(
                    batch_id=batch.batch_id,
                    entities=entities,
                    processing_time_ms=1.0,
                )

        extractor = EchoExtractor()
        batch = _make_batch(2)
        result = await extractor.extract(batch)
        assert result.batch_id == batch.batch_id
        assert len(result.entities) == 2

    def test_abstract_extractor_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            Extractor()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# EntityDeduplicator
# ---------------------------------------------------------------------------


class TestEntityDeduplicator:
    def test_similarity_helper_identical_strings(self) -> None:
        assert _similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_similarity_helper_completely_different(self) -> None:
        assert _similarity("abc", "xyz") == pytest.approx(0.0)

    def test_similarity_helper_partial_match(self) -> None:
        ratio = _similarity("fix the login bug", "fix the login issue")
        assert 0.0 < ratio < 1.0

    def test_new_entities_added_to_registry(self) -> None:
        dedup = EntityDeduplicator()
        task = _make_task(title="Deploy the service")
        unique = dedup.process(MEETING_ID, [task])
        assert len(unique) == 1
        assert dedup.get_all(MEETING_ID) == [task]

    def test_low_confidence_entity_discarded(self) -> None:
        dedup = EntityDeduplicator(min_confidence=0.3)
        task = _make_task(title="Low confidence task", confidence=0.2)
        unique = dedup.process(MEETING_ID, [task])
        assert unique == []
        assert dedup.get_all(MEETING_ID) == []

    def test_duplicate_task_merged(self) -> None:
        dedup = EntityDeduplicator()
        task1 = _make_task(title="fix the login bug", confidence=0.7)
        task2 = _make_task(title="fix the login bug", confidence=0.9)

        dedup.process(MEETING_ID, [task1])
        unique = dedup.process(MEETING_ID, [task2])

        # task2 is a near-duplicate — not returned as new
        assert unique == []
        all_entities = dedup.get_all(MEETING_ID)
        assert len(all_entities) == 1
        # Higher confidence wins
        assert all_entities[0].confidence == pytest.approx(0.9)

    def test_similar_but_not_identical_tasks_merged(self) -> None:
        dedup = EntityDeduplicator(similarity_threshold=0.85)
        task1 = _make_task(title="write unit tests for the auth module")
        task2 = _make_task(title="write unit tests for auth module")

        dedup.process(MEETING_ID, [task1])
        unique = dedup.process(MEETING_ID, [task2])

        # Highly similar titles → treated as duplicate
        assert unique == []

    def test_different_entity_types_not_merged(self) -> None:
        dedup = EntityDeduplicator()
        # Same content key but different entity types
        task = _make_task(title="deploy the service")
        blocker = BlockerEntity(
            meeting_id=MEETING_ID,
            batch_id=BATCH_ID,
            description="deploy the service",
        )
        unique = dedup.process(MEETING_ID, [task, blocker])
        assert len(unique) == 2

    def test_get_all_returns_copy(self) -> None:
        dedup = EntityDeduplicator()
        dedup.process(MEETING_ID, [_make_task()])
        result = dedup.get_all(MEETING_ID)
        result.clear()
        # Modifying the returned list does not affect the registry
        assert len(dedup.get_all(MEETING_ID)) == 1

    def test_clear_removes_all(self) -> None:
        dedup = EntityDeduplicator()
        dedup.process(MEETING_ID, [_make_task(), _make_decision()])
        dedup.clear(MEETING_ID)
        assert dedup.get_all(MEETING_ID) == []

    def test_distinct_meetings_isolated(self) -> None:
        other_meeting = str(uuid4())
        dedup = EntityDeduplicator()
        dedup.process(MEETING_ID, [_make_task(title="Task A")])
        other_task = TaskEntity(
            meeting_id=other_meeting,
            batch_id=BATCH_ID,
            title="Task A",
        )
        unique = dedup.process(other_meeting, [other_task])
        # Same content but different meeting — treated as new
        assert len(unique) == 1


# ---------------------------------------------------------------------------
# BatchCollector tests
# ---------------------------------------------------------------------------


class TestBatchCollector:
    async def test_start_subscribes_to_transcript_topic(self) -> None:
        bus = MockMessageBus()
        extractor = _make_noop_extractor()
        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[extractor],
            batch_window_seconds=30.0,
        )
        await collector.start()
        try:
            topic = f"meeting.{MEETING_ID}.transcript"
            assert any(sub.topic == topic for sub in bus._subscriptions.values())
        finally:
            await collector.stop()

    async def test_stop_unsubscribes(self) -> None:
        bus = MockMessageBus()
        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[],
        )
        await collector.start()
        assert len(bus._subscriptions) == 1
        await collector.stop()
        assert len(bus._subscriptions) == 0

    async def test_published_message_buffered(self) -> None:
        from kutana_core.models.transcript import TranscriptSegment

        bus = MockMessageBus()
        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[],
            batch_window_seconds=60.0,  # Don't auto-flush
        )
        await collector.start()

        # Publish a transcript segment
        seg = TranscriptSegment(
            meeting_id=uuid4(),
            speaker_id="Alice",
            text="Let's ship by Friday.",
            start_time=0.0,
            end_time=3.0,
        )
        await bus.publish(
            f"meeting.{MEETING_ID}.transcript",
            seg.model_dump(mode="json"),
        )

        assert len(collector._buffer) == 1
        assert collector._buffer[0].text == "Let's ship by Friday."
        await collector.stop()

    async def test_process_batch_calls_extractor_and_publishes(self) -> None:
        from kutana_core.models.transcript import TranscriptSegment

        bus = MockMessageBus()

        # Extractor that always returns one task
        class OneTaskExtractor(Extractor):
            @property
            def name(self) -> str:
                return "one-task"

            @property
            def entity_types(self) -> list[str]:
                return ["task"]

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                return ExtractionResult(
                    batch_id=batch.batch_id,
                    entities=[
                        TaskEntity(
                            meeting_id=batch.meeting_id,
                            batch_id=batch.batch_id,
                            title="Ship by Friday",
                        )
                    ],
                    processing_time_ms=5.0,
                )

        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[OneTaskExtractor()],
            batch_window_seconds=60.0,
        )
        await collector.start()

        seg = TranscriptSegment(
            meeting_id=uuid4(),
            speaker_id="Alice",
            text="Let's ship by Friday.",
            start_time=0.0,
            end_time=3.0,
        )
        await bus.publish(
            f"meeting.{MEETING_ID}.transcript",
            seg.model_dump(mode="json"),
        )

        # Manually trigger the batch (bypass the timer)
        await collector._process_batch()

        # Published messages: one to .insights and one to .insights.task
        insight_msgs = [m for m in bus.published if m.topic == f"meeting.{MEETING_ID}.insights"]
        task_msgs = [m for m in bus.published if m.topic == f"meeting.{MEETING_ID}.insights.task"]
        assert len(insight_msgs) == 1
        assert len(task_msgs) == 1

        await collector.stop()

    async def test_final_flush_on_stop(self) -> None:
        from kutana_core.models.transcript import TranscriptSegment

        bus = MockMessageBus()
        results: list[str] = []

        class RecordingExtractor(Extractor):
            @property
            def name(self) -> str:
                return "recorder"

            @property
            def entity_types(self) -> list[str]:
                return []

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                results.append(batch.batch_id)
                return ExtractionResult(
                    batch_id=batch.batch_id,
                    entities=[],
                    processing_time_ms=0.0,
                )

        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[RecordingExtractor()],
            batch_window_seconds=9999.0,
        )
        await collector.start()

        seg = TranscriptSegment(
            meeting_id=uuid4(),
            text="Final segment.",
            start_time=0.0,
            end_time=1.0,
        )
        await bus.publish(
            f"meeting.{MEETING_ID}.transcript",
            seg.model_dump(mode="json"),
        )

        # stop() should flush the remaining segment
        await collector.stop()
        assert len(results) == 1

    async def test_flush_loop_fires_after_window(self) -> None:
        """The flush loop triggers _process_batch when the window elapses."""
        from kutana_core.models.transcript import TranscriptSegment

        bus = MockMessageBus()
        results: list[str] = []

        class RecordingExtractor(Extractor):
            @property
            def name(self) -> str:
                return "recorder"

            @property
            def entity_types(self) -> list[str]:
                return []

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                results.append(batch.batch_id)
                return ExtractionResult(
                    batch_id=batch.batch_id,
                    entities=[],
                    processing_time_ms=0.0,
                )

        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[RecordingExtractor()],
            batch_window_seconds=0.05,  # Very short window
        )
        await collector.start()

        seg = TranscriptSegment(
            meeting_id=uuid4(),
            text="Quick segment.",
            start_time=0.0,
            end_time=1.0,
        )
        await bus.publish(
            f"meeting.{MEETING_ID}.transcript",
            seg.model_dump(mode="json"),
        )

        # Wait long enough for the flush loop to fire
        await asyncio.sleep(0.2)
        await collector.stop()

        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Full pipeline integration test
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Transcript segments → batch → extract → deduplicate → publish."""

    async def test_end_to_end_pipeline(self) -> None:
        from kutana_core.models.transcript import TranscriptSegment

        bus = MockMessageBus()
        dedup = EntityDeduplicator()

        extracted_results: list[ExtractionResult] = []

        class CapturingExtractor(Extractor):
            @property
            def name(self) -> str:
                return "capturing"

            @property
            def entity_types(self) -> list[str]:
                return ["task", "decision"]

            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                entities: list[AnyExtractedEntity] = [
                    TaskEntity(
                        meeting_id=batch.meeting_id,
                        batch_id=batch.batch_id,
                        title="Review the PR",
                    ),
                    DecisionEntity(
                        meeting_id=batch.meeting_id,
                        batch_id=batch.batch_id,
                        summary="Use Redis for caching",
                    ),
                ]
                result = ExtractionResult(
                    batch_id=batch.batch_id,
                    entities=entities,
                    processing_time_ms=10.0,
                )
                extracted_results.append(result)
                return result

        collector = BatchCollector(
            bus=bus,
            meeting_id=MEETING_ID,
            extractors=[CapturingExtractor()],
            batch_window_seconds=9999.0,
        )
        await collector.start()

        # Publish two transcript segments
        for i in range(2):
            seg = TranscriptSegment(
                meeting_id=uuid4(),
                speaker_id=f"spk_{i}",
                text=f"Meeting segment {i}.",
                start_time=float(i * 5),
                end_time=float(i * 5 + 3),
            )
            await bus.publish(
                f"meeting.{MEETING_ID}.transcript",
                seg.model_dump(mode="json"),
            )

        # Trigger batch processing
        await collector._process_batch()

        # 1. Extractor was called
        assert len(extracted_results) == 1
        result = extracted_results[0]
        assert len(result.entities) == 2

        # 2. Deduplicator filters correctly
        unique = dedup.process(MEETING_ID, result.entities)
        assert len(unique) == 2

        # 3. Running same entities again gives no new unique
        unique2 = dedup.process(MEETING_ID, result.entities)
        assert unique2 == []

        # 4. Messages were published to bus
        insight_msgs = [m for m in bus.published if f"meeting.{MEETING_ID}.insights" in m.topic]
        assert len(insight_msgs) >= 2  # base + per-type

        await collector.stop()


# ---------------------------------------------------------------------------
# Helper factory for simple no-op extractor
# ---------------------------------------------------------------------------


def _make_noop_extractor() -> Extractor:
    class NoopExtractor(Extractor):
        @property
        def name(self) -> str:
            return "noop"

        @property
        def entity_types(self) -> list[str]:
            return []

        async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
            return ExtractionResult(
                batch_id=batch.batch_id,
                entities=[],
                processing_time_ms=0.0,
            )

    return NoopExtractor()
