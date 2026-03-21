"""Tests for the LLMExtractor provider (convene-providers)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from convene_core.extraction.types import (
    BatchSegment,
    BlockerEntity,
    DecisionEntity,
    EntityMentionEntity,
    ExtractionResult,
    FollowUpEntity,
    KeyPointEntity,
    QuestionEntity,
    TaskEntity,
    TranscriptBatch,
)
from convene_providers.extraction.llm_extractor import LLMExtractor
from convene_providers.registry import ProviderType, default_registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MEETING_ID = str(uuid4())


def _make_batch(n: int = 2) -> TranscriptBatch:
    return TranscriptBatch(
        meeting_id=MEETING_ID,
        segments=[
            BatchSegment(
                segment_id=str(uuid4()),
                speaker=f"spk_{i}",
                text=f"We need to {['fix the bug', 'deploy the service', 'review the PR'][i % 3]}.",
                start_time=float(i * 10),
                end_time=float(i * 10 + 5),
            )
            for i in range(n)
        ],
    )


def _make_tool_response(tool_input: dict[str, Any]) -> MagicMock:
    """Build a mock Anthropic messages.create response for tool_use."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "extract_meeting_entities"
    tool_block.input = tool_input

    response = MagicMock()
    response.content = [tool_block]
    return response


def _empty_tool_input() -> dict[str, Any]:
    return {
        "tasks": [],
        "decisions": [],
        "questions": [],
        "entity_mentions": [],
        "key_points": [],
        "blockers": [],
        "follow_ups": [],
    }


# ---------------------------------------------------------------------------
# LLMExtractor properties
# ---------------------------------------------------------------------------


class TestLLMExtractorProperties:
    def test_name(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        assert extractor.name == "llm-extractor"

    def test_entity_types(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        expected = {
            "task",
            "decision",
            "question",
            "entity_mention",
            "key_point",
            "blocker",
            "follow_up",
        }
        assert set(extractor.entity_types) == expected

    def test_entity_types_is_list(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        assert isinstance(extractor.entity_types, list)


# ---------------------------------------------------------------------------
# LLMExtractor.extract() — mocked Anthropic client
# ---------------------------------------------------------------------------


class TestLLMExtractorExtract:
    async def test_empty_batch_returns_empty_result(self) -> None:
        """Empty batch short-circuits without calling the API."""
        extractor = LLMExtractor(api_key="test-key")
        empty_batch = TranscriptBatch(meeting_id=MEETING_ID, segments=[])

        result = await extractor.extract(empty_batch)

        assert result.entities == []
        assert result.processing_time_ms == pytest.approx(0.0)
        assert result.batch_id == empty_batch.batch_id

    async def test_extract_returns_extraction_result(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(2)

        mock_response = _make_tool_response(_empty_tool_input())

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert isinstance(result, ExtractionResult)
        assert result.batch_id == batch.batch_id
        assert result.processing_time_ms > 0.0

    async def test_extract_parses_task(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "tasks": [
                {
                    "title": "Deploy to staging",
                    "assignee": "Alice",
                    "priority": "high",
                    "status": "identified",
                }
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        task = result.entities[0]
        assert isinstance(task, TaskEntity)
        assert task.title == "Deploy to staging"
        assert task.assignee == "Alice"
        assert task.priority == "high"
        assert task.meeting_id == MEETING_ID
        assert task.batch_id == batch.batch_id

    async def test_extract_parses_decision(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "decisions": [
                {
                    "summary": "Use PostgreSQL for the database",
                    "participants": ["Alice", "Bob"],
                    "confidence": 0.9,
                }
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        decision = result.entities[0]
        assert isinstance(decision, DecisionEntity)
        assert decision.summary == "Use PostgreSQL for the database"
        assert decision.confidence == pytest.approx(0.9)

    async def test_extract_parses_question(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "questions": [{"text": "When is the release date?", "asker": "Charlie"}],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        question = result.entities[0]
        assert isinstance(question, QuestionEntity)
        assert question.text == "When is the release date?"

    async def test_extract_parses_entity_mention(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "entity_mentions": [
                {"name": "Stripe", "kind": "system", "context": "payment processing"}
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        mention = result.entities[0]
        assert isinstance(mention, EntityMentionEntity)
        assert mention.name == "Stripe"
        assert mention.kind == "system"

    async def test_extract_parses_key_point(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "key_points": [
                {"summary": "We need to refactor auth", "importance": "high"}
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        point = result.entities[0]
        assert isinstance(point, KeyPointEntity)
        assert point.importance == "high"

    async def test_extract_parses_blocker(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "blockers": [
                {"description": "Missing API keys from vendor", "severity": "critical"}
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        blocker = result.entities[0]
        assert isinstance(blocker, BlockerEntity)
        assert blocker.severity == "critical"

    async def test_extract_parses_follow_up(self) -> None:
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "follow_ups": [
                {
                    "description": "Send design mockups to team",
                    "owner": "Diana",
                    "due_context": "by end of week",
                }
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1
        follow_up = result.entities[0]
        assert isinstance(follow_up, FollowUpEntity)
        assert follow_up.owner == "Diana"
        assert follow_up.due_context == "by end of week"

    async def test_extract_mixed_entities(self) -> None:
        """Multiple entity types in a single response are all parsed."""
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(3)

        tool_input = {
            "tasks": [{"title": "Deploy service"}],
            "decisions": [{"summary": "Use Redis"}],
            "questions": [{"text": "When do we ship?"}],
            "entity_mentions": [{"name": "Redis", "kind": "system"}],
            "key_points": [{"summary": "Important architecture note"}],
            "blockers": [{"description": "Infra not ready"}],
            "follow_ups": [{"description": "Check with DevOps"}],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 7
        entity_types = {e.entity_type for e in result.entities}
        assert entity_types == {
            "task",
            "decision",
            "question",
            "entity_mention",
            "key_point",
            "blocker",
            "follow_up",
        }

    async def test_invalid_entity_in_response_skipped(self) -> None:
        """Malformed entities in the LLM response are silently skipped."""
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        tool_input = {
            **_empty_tool_input(),
            "tasks": [
                {"title": "Good task"},  # valid
                {"priority": "high"},  # missing required 'title' → skipped
            ],
        }
        mock_response = _make_tool_response(tool_input)

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert len(result.entities) == 1

    async def test_no_tool_use_block_returns_empty(self) -> None:
        """If the response has no tool_use block, returns empty entities."""
        extractor = LLMExtractor(api_key="test-key")
        batch = _make_batch(1)

        text_block = MagicMock()
        text_block.type = "text"
        mock_response = MagicMock()
        mock_response.content = [text_block]

        with patch.object(
            extractor._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await extractor.extract(batch)

        assert result.entities == []

    async def test_context_segments_included_in_prompt(self) -> None:
        """Context segments are included in the formatted transcript."""
        extractor = LLMExtractor(api_key="test-key")

        ctx_segment = BatchSegment(
            segment_id="prev_1",
            speaker="Alice",
            text="Previous context text.",
            start_time=0.0,
            end_time=2.0,
        )
        batch = TranscriptBatch(
            meeting_id=MEETING_ID,
            segments=[
                BatchSegment(
                    segment_id="curr_1",
                    speaker="Bob",
                    text="Current segment.",
                    start_time=30.0,
                    end_time=33.0,
                )
            ],
            context_segments=[ctx_segment],
        )

        captured_messages: list[Any] = []

        async def mock_create(**kwargs: Any) -> MagicMock:
            captured_messages.append(kwargs.get("messages", []))
            return _make_tool_response(_empty_tool_input())

        with patch.object(
            extractor._client.messages, "create", new=mock_create
        ):
            await extractor.extract(batch)

        assert len(captured_messages) == 1
        user_content = captured_messages[0][0]["content"]
        assert "Previous context text." in user_content
        assert "Current segment." in user_content


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_extractor_type_exists(self) -> None:
        assert ProviderType.EXTRACTOR == "extractor"

    def test_llm_extractor_registered(self) -> None:
        assert default_registry.is_registered(ProviderType.EXTRACTOR, "llm")

    def test_create_llm_extractor_from_registry(self) -> None:
        extractor = default_registry.create(
            ProviderType.EXTRACTOR, "llm", api_key="test-key"
        )
        assert isinstance(extractor, LLMExtractor)
        assert extractor.name == "llm-extractor"

    def test_list_extractors(self) -> None:
        extractors = default_registry.list_providers(ProviderType.EXTRACTOR)
        assert "llm" in extractors
