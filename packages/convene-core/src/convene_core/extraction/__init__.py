"""Meeting Insight Stream extraction pipeline for Convene AI.

Provides the entity schema, Extractor ABC, BatchCollector, and
EntityDeduplicator that together form the extraction pipeline layer.
"""

from __future__ import annotations

from convene_core.extraction.abc import Extractor
from convene_core.extraction.collector import BatchCollector
from convene_core.extraction.deduplicator import EntityDeduplicator
from convene_core.extraction.types import (
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

__all__ = [
    "AnyExtractedEntity",
    "BatchCollector",
    "BatchSegment",
    "BlockerEntity",
    "DecisionEntity",
    "EntityDeduplicator",
    "EntityMentionEntity",
    "ExtractedEntity",
    "ExtractionResult",
    "Extractor",
    "FollowUpEntity",
    "KeyPointEntity",
    "QuestionEntity",
    "TaskEntity",
    "TranscriptBatch",
]
