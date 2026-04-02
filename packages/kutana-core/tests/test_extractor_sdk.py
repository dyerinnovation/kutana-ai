"""Tests for the custom extractor SDK and ExtractorLoader."""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, ClassVar

import pytest

from kutana_core.extraction.abc import Extractor
from kutana_core.extraction.loader import (
    ENTRY_POINT_GROUP,
    ExtractorLoader,
    ExtractorValidationError,
    validate_extractor,
)
from kutana_core.extraction.sdk import (
    SimpleExtractor,
    _FunctionExtractor,
    extractor,
    make_blocker,
    make_decision,
    make_entity_mention,
    make_follow_up,
    make_key_point,
    make_question,
    make_task,
)
from kutana_core.extraction.types import (
    BatchSegment,
    ExtractionResult,
    TranscriptBatch,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_batch(
    meeting_id: str = "meet-test",
    texts: list[str] | None = None,
) -> TranscriptBatch:
    """Build a simple TranscriptBatch for use in tests."""
    segments = [
        BatchSegment(
            segment_id=f"seg-{i}",
            speaker="Alice",
            text=t,
            start_time=float(i),
            end_time=float(i + 1),
        )
        for i, t in enumerate(texts or ["Hello world"])
    ]
    return TranscriptBatch(meeting_id=meeting_id, segments=segments)


# ---------------------------------------------------------------------------
# validate_extractor
# ---------------------------------------------------------------------------


class TestValidateExtractor:
    """Tests for the validate_extractor() function."""

    def test_valid_simple_extractor_passes(self) -> None:
        """A properly implemented SimpleExtractor passes validation."""

        class GoodExtractor(SimpleExtractor):
            name = "good"
            entity_types: ClassVar[list[str]] = ["task"]

        validate_extractor(GoodExtractor)

    def test_non_class_raises(self) -> None:
        """validate_extractor raises if given a non-class object."""
        with pytest.raises(ExtractorValidationError, match="must be a class"):
            validate_extractor("not-a-class")  # type: ignore[arg-type]

    def test_non_extractor_subclass_raises(self) -> None:
        """validate_extractor raises if cls does not subclass Extractor."""

        class NotAnExtractor:
            pass

        with pytest.raises(ExtractorValidationError, match="must subclass Extractor"):
            validate_extractor(NotAnExtractor)

    def test_abstract_extractor_raises(self) -> None:
        """validate_extractor raises if cls has un-implemented abstract methods."""

        class PartialExtractor(Extractor):
            # Missing: extract, name, entity_types
            pass

        with pytest.raises(ExtractorValidationError, match="unimplemented abstract"):
            validate_extractor(PartialExtractor)  # type: ignore[type-abstract]

    def test_extractor_with_empty_name_raises(self) -> None:
        """validate_extractor raises if name property returns empty string."""

        class EmptyNameExtractor(SimpleExtractor):
            name = ""
            entity_types: ClassVar[list[str]] = ["task"]

        # Bypass the SimpleExtractor __init_subclass__ warning:
        # validate_extractor should still catch it via instance check
        EmptyNameExtractor.name = ""  # override the warning
        # validate_extractor does runtime check only when no-arg __init__
        # This should raise because name is empty string
        with pytest.raises(ExtractorValidationError, match="name property"):
            validate_extractor(EmptyNameExtractor)

    def test_extractor_with_empty_entity_types_raises(self) -> None:
        """validate_extractor raises if entity_types returns empty list."""

        class EmptyTypesExtractor(SimpleExtractor):
            name = "nonempty"
            entity_types: ClassVar[list[str]] = []

        EmptyTypesExtractor.entity_types = []
        with pytest.raises(ExtractorValidationError, match="entity_types"):
            validate_extractor(EmptyTypesExtractor)


# ---------------------------------------------------------------------------
# SimpleExtractor
# ---------------------------------------------------------------------------


class TestSimpleExtractor:
    """Tests for the SimpleExtractor base class."""

    async def test_default_extract_returns_empty_result(self) -> None:
        """SimpleExtractor.extract() returns an empty ExtractionResult by default."""

        class MyExtractor(SimpleExtractor):
            name = "my-extractor"
            entity_types: ClassVar[list[str]] = ["task"]

        extractor_instance = MyExtractor()
        batch = _make_batch()
        result = await extractor_instance.extract(batch)
        assert isinstance(result, ExtractionResult)
        assert result.entities == []
        assert result.batch_id == batch.batch_id

    async def test_timed_result_sets_processing_time(self) -> None:
        """timed_result() sets processing_time_ms to a non-negative value."""
        import time

        class TimedExtractor(SimpleExtractor):
            name = "timed"
            entity_types: ClassVar[list[str]] = ["task"]

        ext = TimedExtractor()
        batch = _make_batch()
        start = time.monotonic()
        result = ext.timed_result(batch, [], start)
        assert result.processing_time_ms >= 0.0

    def test_simple_extractor_has_name_property(self) -> None:
        """SimpleExtractor subclass name attribute is accessible via the name property."""

        class NExtractor(SimpleExtractor):
            name = "test-name"
            entity_types: ClassVar[list[str]] = ["task"]

        ext = NExtractor()
        assert ext.name == "test-name"

    def test_simple_extractor_has_entity_types_property(self) -> None:
        """SimpleExtractor entity_types attribute is accessible as a property."""

        class TExtractor(SimpleExtractor):
            name = "t"
            entity_types: ClassVar[list[str]] = ["task", "decision"]

        ext = TExtractor()
        assert ext.entity_types == ["task", "decision"]


# ---------------------------------------------------------------------------
# @extractor decorator
# ---------------------------------------------------------------------------


class TestExtractorDecorator:
    """Tests for the @extractor function decorator."""

    def test_decorator_returns_extractor_instance(self) -> None:
        """@extractor wraps the function in a _FunctionExtractor instance."""

        @extractor(name="deco-test", entity_types=["key_point"])
        async def my_fn(batch: TranscriptBatch) -> ExtractionResult:
            return ExtractionResult(batch_id=batch.batch_id, entities=[], processing_time_ms=0.0)

        assert isinstance(my_fn, _FunctionExtractor)
        assert isinstance(my_fn, Extractor)

    def test_decorator_sets_name(self) -> None:
        """@extractor sets the name property on the returned instance."""

        @extractor(name="my-decorator-extractor", entity_types=["task"])
        async def fn(batch: TranscriptBatch) -> ExtractionResult:
            return ExtractionResult(batch_id=batch.batch_id, entities=[], processing_time_ms=0.0)

        assert fn.name == "my-decorator-extractor"

    def test_decorator_sets_entity_types(self) -> None:
        """@extractor sets the entity_types property on the returned instance."""

        @extractor(name="e", entity_types=["decision", "blocker"])
        async def fn(batch: TranscriptBatch) -> ExtractionResult:
            return ExtractionResult(batch_id=batch.batch_id, entities=[], processing_time_ms=0.0)

        assert fn.entity_types == ["decision", "blocker"]

    async def test_decorator_delegates_extract_to_function(self) -> None:
        """@extractor delegates extract() calls to the wrapped function."""
        calls: list[TranscriptBatch] = []

        @extractor(name="call-logger", entity_types=["task"])
        async def fn(batch: TranscriptBatch) -> ExtractionResult:
            calls.append(batch)
            return ExtractionResult(batch_id=batch.batch_id, entities=[], processing_time_ms=0.0)

        batch = _make_batch()
        await fn.extract(batch)
        assert len(calls) == 1
        assert calls[0] is batch

    def test_decorator_empty_name_raises(self) -> None:
        """@extractor raises ValueError for an empty name."""
        with pytest.raises(ValueError, match="non-empty name"):

            @extractor(name="", entity_types=["task"])
            async def fn(batch: TranscriptBatch) -> ExtractionResult:  # type: ignore[return]
                ...

    def test_decorator_empty_entity_types_raises(self) -> None:
        """@extractor raises ValueError for an empty entity_types list."""
        with pytest.raises(ValueError, match="non-empty entity_types"):

            @extractor(name="valid-name", entity_types=[])
            async def fn(batch: TranscriptBatch) -> ExtractionResult:  # type: ignore[return]
                ...


# ---------------------------------------------------------------------------
# Entity factory helpers
# ---------------------------------------------------------------------------


class TestEntityFactories:
    """Tests for the make_* factory functions."""

    def test_make_task_returns_task_entity(self) -> None:
        batch = _make_batch()
        entity = make_task(batch, title="Fix bug", assignee="Bob", priority="high")
        assert entity.entity_type == "task"
        assert entity.title == "Fix bug"
        assert entity.assignee == "Bob"
        assert entity.priority == "high"
        assert entity.meeting_id == batch.meeting_id
        assert entity.batch_id == batch.batch_id

    def test_make_decision_returns_decision_entity(self) -> None:
        batch = _make_batch()
        entity = make_decision(batch, summary="Use PostgreSQL", participants=["Alice"])
        assert entity.entity_type == "decision"
        assert entity.summary == "Use PostgreSQL"
        assert "Alice" in entity.participants

    def test_make_question_returns_question_entity(self) -> None:
        batch = _make_batch()
        entity = make_question(batch, text="What is the deadline?", asker="Charlie")
        assert entity.entity_type == "question"
        assert entity.text == "What is the deadline?"
        assert entity.asker == "Charlie"

    def test_make_key_point_returns_key_point_entity(self) -> None:
        batch = _make_batch()
        entity = make_key_point(batch, summary="Security is paramount", importance="high")
        assert entity.entity_type == "key_point"
        assert entity.summary == "Security is paramount"
        assert entity.importance == "high"

    def test_make_blocker_returns_blocker_entity(self) -> None:
        batch = _make_batch()
        entity = make_blocker(batch, description="API is down", severity="critical")
        assert entity.entity_type == "blocker"
        assert entity.description == "API is down"
        assert entity.severity == "critical"

    def test_make_follow_up_returns_follow_up_entity(self) -> None:
        batch = _make_batch()
        entity = make_follow_up(batch, description="Send report", owner="Dana")
        assert entity.entity_type == "follow_up"
        assert entity.description == "Send report"
        assert entity.owner == "Dana"

    def test_make_entity_mention_returns_entity_mention_entity(self) -> None:
        batch = _make_batch()
        entity = make_entity_mention(batch, name="Anthropic", kind="org")
        assert entity.entity_type == "entity_mention"
        assert entity.name == "Anthropic"
        assert entity.kind == "org"

    def test_factory_confidence_defaults_are_valid(self) -> None:
        """All factory defaults produce entities with confidence in [0, 1]."""
        batch = _make_batch()
        entities = [
            make_task(batch, "t"),
            make_decision(batch, "d"),
            make_question(batch, "q"),
            make_key_point(batch, "k"),
            make_blocker(batch, "b"),
            make_follow_up(batch, "f"),
            make_entity_mention(batch, "E", "concept"),
        ]
        for ent in entities:
            assert 0.0 <= ent.confidence <= 1.0

    def test_factory_inherits_meeting_and_batch_ids(self) -> None:
        """Factory functions inherit meeting_id and batch_id from the batch."""
        batch = _make_batch(meeting_id="meeting-xyz")
        task = make_task(batch, "Do something")
        assert task.meeting_id == "meeting-xyz"
        assert task.batch_id == batch.batch_id


# ---------------------------------------------------------------------------
# ExtractorLoader — registration
# ---------------------------------------------------------------------------


class TestExtractorLoaderRegister:
    """Tests for ExtractorLoader.register."""

    def test_register_valid_extractor(self) -> None:
        """register() accepts a valid SimpleExtractor subclass."""

        class ValidExt(SimpleExtractor):
            name = "valid"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(ValidExt)
        assert loader.is_registered("valid")

    def test_register_with_explicit_name(self) -> None:
        """register(name=...) uses the provided name."""

        class AnyExt(SimpleExtractor):
            name = "auto-name"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(AnyExt, name="custom-name")
        assert loader.is_registered("custom-name")
        assert not loader.is_registered("auto-name")

    def test_register_duplicate_raises(self) -> None:
        """register() raises ValueError for duplicate names."""

        class Dup(SimpleExtractor):
            name = "dup"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(Dup)
        with pytest.raises(ValueError, match="already registered"):
            loader.register(Dup)

    def test_register_invalid_extractor_raises(self) -> None:
        """register() raises ExtractorValidationError for invalid classes."""

        class NotAnExtractor:
            pass

        loader = ExtractorLoader()
        with pytest.raises(ExtractorValidationError):
            loader.register(NotAnExtractor)  # type: ignore[arg-type]

    def test_register_or_replace_replaces_existing(self) -> None:
        """register_or_replace() replaces an existing extractor without raising."""

        class V1(SimpleExtractor):
            name = "hot"
            entity_types: ClassVar[list[str]] = ["task"]

        class V2(SimpleExtractor):
            name = "hot"
            entity_types: ClassVar[list[str]] = ["task", "decision"]

        loader = ExtractorLoader()
        loader.register(V1)
        loader.register_or_replace(V2)
        assert loader.extractors["hot"] is V2

    def test_unregister_removes_extractor(self) -> None:
        """unregister() removes an extractor from the registry."""

        class TmpExt(SimpleExtractor):
            name = "tmp"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(TmpExt)
        loader.unregister("tmp")
        assert not loader.is_registered("tmp")

    def test_unregister_nonexistent_raises(self) -> None:
        """unregister() raises KeyError for unknown names."""
        loader = ExtractorLoader()
        with pytest.raises(KeyError, match="No extractor registered"):
            loader.unregister("does-not-exist")


# ---------------------------------------------------------------------------
# ExtractorLoader — creation
# ---------------------------------------------------------------------------


class TestExtractorLoaderCreate:
    """Tests for ExtractorLoader.create."""

    def test_create_instantiates_registered_extractor(self) -> None:
        """create() returns an instance of the registered class."""

        class MyExt(SimpleExtractor):
            name = "my-ext"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(MyExt)
        instance = loader.create("my-ext")
        assert isinstance(instance, MyExt)

    def test_create_passes_kwargs_to_constructor(self) -> None:
        """create() forwards keyword arguments to the constructor."""

        class Configurable(SimpleExtractor):
            name = "configurable"
            entity_types: ClassVar[list[str]] = ["task"]

            def __init__(self, threshold: float = 0.5) -> None:
                self.threshold = threshold

        loader = ExtractorLoader()
        loader.register(Configurable)
        instance = loader.create("configurable", threshold=0.9)
        assert instance.threshold == 0.9  # type: ignore[attr-defined]

    def test_create_unknown_raises(self) -> None:
        """create() raises KeyError for unregistered names."""
        loader = ExtractorLoader()
        with pytest.raises(KeyError, match="No extractor registered"):
            loader.create("nonexistent")


# ---------------------------------------------------------------------------
# ExtractorLoader — file loading
# ---------------------------------------------------------------------------


class TestExtractorLoaderFileLoading:
    """Tests for ExtractorLoader.load_from_file."""

    def test_load_from_valid_file(self) -> None:
        """load_from_file() discovers and registers extractors from a .py file."""
        code = textwrap.dedent("""\
            from kutana_core.extraction.sdk import SimpleExtractor
            from kutana_core.extraction.types import ExtractionResult, TranscriptBatch

            class FileLoadedExtractor(SimpleExtractor):
                name = "file-loaded"
                entity_types: ClassVar[list[str]] = ["task"]

                async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                    return ExtractionResult(batch_id=batch.batch_id, entities=[], processing_time_ms=0.0)
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            loader = ExtractorLoader()
            loaded = loader.load_from_file(tmp_path)
            assert len(loaded) == 1
            assert loader.is_registered("file-loaded")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_from_nonexistent_file_raises(self) -> None:
        """load_from_file() raises FileNotFoundError for missing files."""
        loader = ExtractorLoader()
        with pytest.raises(FileNotFoundError, match="not found"):
            loader.load_from_file("/nonexistent/path/extractor.py")

    def test_load_from_file_with_no_extractors_returns_empty(self) -> None:
        """load_from_file() returns [] when no Extractor subclasses are found."""
        code = "x = 1  # no extractor here\n"
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            loader = ExtractorLoader()
            loaded = loader.load_from_file(tmp_path)
            assert loaded == []
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_from_file_hot_reload(self) -> None:
        """load_from_file() can re-load a modified extractor (hot-reload)."""
        code_v1 = textwrap.dedent("""\
            from kutana_core.extraction.sdk import SimpleExtractor
            from kutana_core.extraction.types import ExtractionResult, TranscriptBatch

            class HotExtractor(SimpleExtractor):
                name = "hot-reload"
                entity_types: ClassVar[list[str]] = ["task"]
                version = "v1"
        """)
        code_v2 = textwrap.dedent("""\
            from kutana_core.extraction.sdk import SimpleExtractor
            from kutana_core.extraction.types import ExtractionResult, TranscriptBatch

            class HotExtractor(SimpleExtractor):
                name = "hot-reload"
                entity_types: ClassVar[list[str]] = ["task", "decision"]
                version = "v2"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False
        ) as f:
            f.write(code_v1)
            tmp_path = f.name

        try:
            loader = ExtractorLoader()
            loader.load_from_file(tmp_path)
            assert loader.is_registered("hot-reload")
            v1_cls = loader.extractors["hot-reload"]

            # Overwrite file with v2 content
            Path(tmp_path).write_text(code_v2)
            loader.load_from_file(tmp_path)
            v2_cls = loader.extractors["hot-reload"]

            assert v2_cls is not v1_cls
            assert v2_cls.entity_types == ["task", "decision"]  # type: ignore[attr-defined]
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# ExtractorLoader — entry point loading
# ---------------------------------------------------------------------------


class TestExtractorLoaderEntryPoints:
    """Tests for ExtractorLoader.load_from_entry_points."""

    def test_load_from_entry_points_calls_importlib_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_from_entry_points() reads the 'kutana.extractors' group."""

        class MockEP:
            name = "mock-ep"
            value = "mock.module:MockClass"

            def load(self) -> Any:
                class MockExtractor(SimpleExtractor):
                    name = "mock-ep"
                    entity_types: ClassVar[list[str]] = ["task"]

                return MockExtractor

        def mock_entry_points(group: str) -> list[Any]:
            if group == ENTRY_POINT_GROUP:
                return [MockEP()]
            return []

        monkeypatch.setattr(
            "kutana_core.extraction.loader.importlib.metadata.entry_points",
            mock_entry_points,
        )
        loader = ExtractorLoader()
        loaded = loader.load_from_entry_points()
        assert "mock-ep" in loaded
        assert loader.is_registered("mock-ep")

    def test_load_from_entry_points_skips_invalid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_from_entry_points() skips entry points that fail to load."""

        class BadEP:
            name = "bad-ep"
            value = "nonexistent.module:SomeClass"

            def load(self) -> Any:
                raise ImportError("module not found")

        def mock_entry_points(group: str) -> list[Any]:
            return [BadEP()]

        monkeypatch.setattr(
            "kutana_core.extraction.loader.importlib.metadata.entry_points",
            mock_entry_points,
        )
        loader = ExtractorLoader()
        loaded = loader.load_from_entry_points()
        assert loaded == []  # Bad EP was skipped


# ---------------------------------------------------------------------------
# ExtractorLoader — introspection
# ---------------------------------------------------------------------------


class TestExtractorLoaderIntrospection:
    """Tests for ExtractorLoader.extractors and is_registered."""

    def test_extractors_returns_snapshot(self) -> None:
        """extractors property returns a snapshot (mutations don't affect registry)."""

        class EE(SimpleExtractor):
            name = "snap"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(EE)
        snapshot = loader.extractors
        snapshot["extra"] = EE  # type: ignore[assignment]
        assert "extra" not in loader.extractors

    def test_is_registered_returns_false_for_unknown(self) -> None:
        loader = ExtractorLoader()
        assert not loader.is_registered("nope")

    def test_repr_shows_registered_names(self) -> None:
        """repr() lists registered extractor names."""

        class R(SimpleExtractor):
            name = "repr-test"
            entity_types: ClassVar[list[str]] = ["task"]

        loader = ExtractorLoader()
        loader.register(R)
        assert "repr-test" in repr(loader)


# ---------------------------------------------------------------------------
# Compliance extractor (integration smoke test)
# ---------------------------------------------------------------------------


class TestComplianceExtractor:
    """Smoke tests for the example ComplianceExtractor."""

    async def test_compliance_extractor_finds_gdpr(self) -> None:
        """ComplianceExtractor extracts entities from GDPR-mentioning segments."""
        # Import from examples
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "examples" / "custom-extractors"))
        try:
            from compliance_extractor import ComplianceExtractor  # type: ignore[import]
        except ImportError:
            pytest.skip("compliance_extractor not found in examples/")
        finally:
            sys.path.pop(0)

        ext = ComplianceExtractor()
        batch = _make_batch(
            texts=[
                "We need to ensure GDPR compliance before the launch.",
                "The weather is nice today.",
                "We also need HIPAA and PCI-DSS sign-off.",
            ]
        )
        result = await ext.extract(batch)
        assert len(result.entities) == 2  # seg 0 and seg 2
        assert all(e.entity_type == "key_point" for e in result.entities)

    async def test_compliance_extractor_empty_batch(self) -> None:
        """ComplianceExtractor returns empty result for batch with no compliance text."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "examples" / "custom-extractors"))
        try:
            from compliance_extractor import ComplianceExtractor  # type: ignore[import]
        except ImportError:
            pytest.skip("compliance_extractor not found in examples/")
        finally:
            sys.path.pop(0)

        ext = ComplianceExtractor()
        batch = _make_batch(texts=["Good morning.", "Let's discuss the product roadmap."])
        result = await ext.extract(batch)
        assert result.entities == []

    async def test_compliance_extractor_is_valid_extractor(self) -> None:
        """ComplianceExtractor passes validate_extractor."""
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "examples" / "custom-extractors"))
        try:
            from compliance_extractor import ComplianceExtractor  # type: ignore[import]
        except ImportError:
            pytest.skip("compliance_extractor not found in examples/")
        finally:
            sys.path.pop(0)

        validate_extractor(ComplianceExtractor)

    def test_compliance_extractor_loadable_via_loader(self) -> None:
        """ExtractorLoader can load ComplianceExtractor from the examples file."""
        examples_path = (
            Path(__file__).parent.parent.parent.parent.parent
            / "examples"
            / "custom-extractors"
            / "compliance_extractor.py"
        )
        if not examples_path.exists():
            pytest.skip("compliance_extractor.py not found")

        loader = ExtractorLoader()
        loaded = loader.load_from_file(examples_path)
        assert "compliance" in loaded or any("compliance" in n for n in loaded)
