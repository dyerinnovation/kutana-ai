"""Abstract base class for entity extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from convene_core.extraction.types import ExtractionResult, TranscriptBatch


class Extractor(ABC):
    """Abstract base class for extraction pipeline providers.

    Implementors receive a ``TranscriptBatch`` (a windowed slice of meeting
    transcript segments) and return an ``ExtractionResult`` containing all
    entities found within that window.

    The ``name`` and ``entity_types`` properties enable the ``BatchCollector``
    to route results and log which extractor produced which entity types.

    Example::

        class MyExtractor(Extractor):
            async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
                ...

            @property
            def name(self) -> str:
                return "my-extractor"

            @property
            def entity_types(self) -> list[str]:
                return ["task", "question"]
    """

    @abstractmethod
    async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
        """Extract entities from a transcript batch.

        Args:
            batch: The windowed transcript batch to process.

        Returns:
            An ``ExtractionResult`` containing all entities found.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this extractor instance.

        Used in logging and for routing insights to the correct topic.
        """
        ...

    @property
    @abstractmethod
    def entity_types(self) -> list[str]:
        """Entity type names this extractor is capable of producing.

        Used by the ``BatchCollector`` to announce which topics will receive
        messages after extraction.
        """
        ...
