"""Entity deduplicator for the Meeting Insight Stream pipeline.

Maintains a per-meeting running set of extracted entities and filters
incoming batches to remove near-duplicate entries.  Similarity is measured
by comparing each entity's ``content_key()`` using ``difflib.SequenceMatcher``.
"""

from __future__ import annotations

import difflib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kutana_core.extraction.types import AnyExtractedEntity

logger = logging.getLogger(__name__)

_DEFAULT_SIMILARITY_THRESHOLD = 0.85
_DEFAULT_MIN_CONFIDENCE = 0.3


def _similarity(a: str, b: str) -> float:
    """Return the similarity ratio between two strings.

    Uses ``difflib.SequenceMatcher`` which gives a value in [0, 1].

    Args:
        a: First string.
        b: Second string.

    Returns:
        Ratio in range 0.0 (completely different) to 1.0 (identical).
    """
    return difflib.SequenceMatcher(None, a, b).ratio()


class EntityDeduplicator:
    """Deduplicates extracted entities across batches within a meeting.

    Keeps an in-memory registry of all seen entities per meeting.  When new
    entities arrive, each one is checked against the existing set:

    - Entities below ``min_confidence`` are discarded.
    - Entities whose ``content_key()`` is similar (≥ ``similarity_threshold``)
      to an already-seen entity of the same type are treated as duplicates.
      The higher-confidence version wins; the registry entry is updated.
    - Genuinely new entities are added to the registry and returned.

    Args:
        min_confidence: Entities with confidence below this threshold are
            discarded.  Defaults to 0.3.
        similarity_threshold: Minimum similarity ratio for two entities to be
            considered duplicates.  Defaults to 0.85.
    """

    def __init__(
        self,
        min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
        similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        """Initialize the deduplicator."""
        self._min_confidence = min_confidence
        self._similarity_threshold = similarity_threshold
        # meeting_id → list of deduplicated entities seen so far
        self._entities: dict[str, list[AnyExtractedEntity]] = {}

    def process(
        self,
        meeting_id: str,
        new_entities: list[AnyExtractedEntity],
    ) -> list[AnyExtractedEntity]:
        """Filter and register a list of newly extracted entities.

        Args:
            meeting_id: Meeting these entities belong to.
            new_entities: Entities from the latest extraction batch.

        Returns:
            The subset of ``new_entities`` that are genuinely new (not
            duplicates of anything already seen for this meeting).
        """
        existing = self._entities.setdefault(meeting_id, [])
        unique_new: list[AnyExtractedEntity] = []

        for entity in new_entities:
            # Drop low-confidence entities outright
            if entity.confidence < self._min_confidence:
                logger.debug(
                    "Discarding low-confidence %s entity (%.2f < %.2f)",
                    entity.entity_type,
                    entity.confidence,
                    self._min_confidence,
                )
                continue

            duplicate = self._find_duplicate(entity, existing)
            if duplicate is not None:
                # Merge: replace with the higher-confidence version
                merged = self._merge(duplicate, entity)
                idx = existing.index(duplicate)
                existing[idx] = merged
                logger.debug(
                    "Merged duplicate %s entity (keeping confidence=%.2f)",
                    entity.entity_type,
                    merged.confidence,
                )
            else:
                unique_new.append(entity)
                existing.append(entity)

        return unique_new

    def get_all(self, meeting_id: str) -> list[AnyExtractedEntity]:
        """Return all deduplicated entities seen for a meeting.

        Args:
            meeting_id: The meeting to query.

        Returns:
            A copy of the entity list (modifications do not affect the registry).
        """
        return list(self._entities.get(meeting_id, []))

    def clear(self, meeting_id: str) -> None:
        """Remove all stored entities for a meeting.

        Args:
            meeting_id: The meeting to clear.
        """
        self._entities.pop(meeting_id, None)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_duplicate(
        self,
        entity: AnyExtractedEntity,
        existing: list[AnyExtractedEntity],
    ) -> AnyExtractedEntity | None:
        """Find an existing entity that is a near-duplicate of ``entity``.

        Only compares entities with the same ``entity_type``.

        Args:
            entity: The incoming entity to match against.
            existing: Registry of already-seen entities.

        Returns:
            The matching existing entity, or ``None`` if no duplicate found.
        """
        entity_key = entity.content_key()
        if not entity_key:
            return None

        for candidate in existing:
            if candidate.entity_type != entity.entity_type:
                continue
            candidate_key = candidate.content_key()
            if not candidate_key:
                continue
            if _similarity(entity_key, candidate_key) >= self._similarity_threshold:
                return candidate

        return None

    def _merge(
        self,
        existing: AnyExtractedEntity,
        incoming: AnyExtractedEntity,
    ) -> AnyExtractedEntity:
        """Merge two duplicate entities, keeping the higher-confidence version.

        Args:
            existing: The entity currently in the registry.
            incoming: The newly extracted entity.

        Returns:
            The entity with the higher confidence (unchanged if equal).
        """
        if incoming.confidence > existing.confidence:
            return incoming
        return existing
