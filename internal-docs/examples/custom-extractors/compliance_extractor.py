"""Example custom extractor: Compliance Mention Detector.

This file demonstrates how to build a custom Kutana AI extractor using
the SDK helpers.  The ``ComplianceExtractor`` scans meeting transcripts for
regulatory and compliance-related language and emits ``key_point`` entities
for each mention found.

How to use this extractor
-------------------------

1. **Register at startup** (standalone / service integration)::

       from kutana_core.extraction.loader import ExtractorLoader

       loader = ExtractorLoader()
       loader.load_from_file("examples/custom-extractors/compliance_extractor.py")
       extractor = loader.create("compliance")

2. **Install as a package entry point** — add to your ``pyproject.toml``::

       [project.entry-points."kutana.extractors"]
       compliance = "my_package.compliance_extractor:ComplianceExtractor"

   Then run ``loader.load_from_entry_points()`` at startup.

3. **Register directly** (in tests or notebook environments)::

       from kutana_core.extraction.loader import ExtractorLoader
       loader = ExtractorLoader()
       loader.register(ComplianceExtractor)

How to call the extractor
-------------------------
::

    from kutana_core.extraction.types import BatchSegment, TranscriptBatch

    batch = TranscriptBatch(
        meeting_id="meet-123",
        segments=[
            BatchSegment(
                segment_id="seg-1",
                speaker="Alice",
                text="We need to ensure GDPR compliance before launch.",
                start_time=0.0,
                end_time=5.0,
            )
        ],
    )

    result = await extractor.extract(batch)
    for entity in result.entities:
        print(entity)
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, ClassVar

from kutana_core.extraction.sdk import SimpleExtractor, make_key_point
from kutana_core.extraction.types import ExtractionResult, TranscriptBatch

if TYPE_CHECKING:
    from kutana_core.extraction.abc import Extractor

# ---------------------------------------------------------------------------
# Compliance keyword patterns
# ---------------------------------------------------------------------------

#: Regulatory frameworks and their common abbreviations.
_REGULATION_PATTERNS: list[str] = [
    r"\bGDPR\b",
    r"\bCCPA\b",
    r"\bHIPAA\b",
    r"\bSOC\s*2\b",
    r"\bSOX\b",
    r"\bPCI[\s-]?DSS\b",
    r"\bFERPA\b",
    r"\bGLBA\b",
    r"\bISO\s*27001\b",
    r"\bNIST\b",
    r"\bFIPS\b",
]

#: Compliance-related action words that indicate a compliance discussion.
_ACTION_KEYWORDS: list[str] = [
    "compliance",
    "compliant",
    "regulation",
    "regulatory",
    "audit",
    "policy",
    "privacy",
    "data protection",
    "data retention",
    "breach",
    "violation",
    "infringement",
    "consent",
    "right to be forgotten",
    "data subject",
    "controller",
    "processor",
    "encryption",
    "access control",
    "due diligence",
    "risk assessment",
    "pen test",
    "penetration test",
    "vulnerability",
    "security review",
    "legal hold",
    "eDiscovery",
    "data residency",
    "sovereignty",
]

# Precompile all patterns for efficiency
_REGULATION_RE = re.compile("|".join(_REGULATION_PATTERNS), re.IGNORECASE)
_ACTION_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _ACTION_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _extract_mentions(text: str) -> list[str]:
    """Find all compliance-related terms mentioned in *text*.

    Args:
        text: Transcript text to scan.

    Returns:
        De-duplicated list of matched terms in the order they first appeared.
    """
    seen: set[str] = set()
    mentions: list[str] = []

    for match in _REGULATION_RE.finditer(text):
        term = match.group().strip().upper()
        if term not in seen:
            seen.add(term)
            mentions.append(term)

    for match in _ACTION_RE.finditer(text):
        term = match.group().strip().lower()
        if term not in seen:
            seen.add(term)
            mentions.append(term)

    return mentions


# ---------------------------------------------------------------------------
# ComplianceExtractor — class-based style (SimpleExtractor subclass)
# ---------------------------------------------------------------------------


class ComplianceExtractor(SimpleExtractor):
    """Scans meeting transcripts for regulatory and compliance-related language.

    Emits a ``key_point`` entity for each transcript segment that contains
    compliance-relevant terminology (regulation names, audit language,
    privacy keywords, etc.).

    Entity types produced:
        - ``key_point`` — one per segment containing compliance language

    This extractor requires no external API calls: it uses purely rule-based
    keyword matching and is safe to run at high frequency without incurring
    per-call costs.

    Attributes:
        name: Registered name for this extractor (``"compliance"``).
        entity_types: List of entity types produced (``["key_point"]``).
        min_confidence: Minimum confidence score assigned to extracted entities.
            Increases with the number of distinct terms found in a segment.

    Example::

        extractor = ComplianceExtractor()
        result = await extractor.extract(batch)
    """

    # SimpleExtractor reads these class attributes via the name/entity_types
    # abstract properties.
    name: ClassVar[str] = "compliance"
    entity_types: ClassVar[list[str]] = ["key_point"]

    #: Base confidence assigned when one keyword is found in a segment.
    min_confidence: float = 0.70
    #: Maximum confidence cap.
    max_confidence: float = 0.95

    def __init__(
        self,
        min_confidence: float = 0.70,
        max_confidence: float = 0.95,
    ) -> None:
        """Initialize the compliance extractor.

        Args:
            min_confidence: Confidence assigned for a single keyword match.
            max_confidence: Cap on confidence regardless of keyword count.
        """
        # SimpleExtractor has no required __init__ arguments
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence

    async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
        """Extract compliance mentions from each segment in the batch.

        For each segment containing at least one compliance keyword or
        regulation name, a ``key_point`` entity is emitted summarizing the
        compliance language found.

        Confidence scales with the number of distinct terms found:
        - 1 term: ``min_confidence``
        - 2+ terms: scales toward ``max_confidence``

        Args:
            batch: The windowed transcript batch to process.

        Returns:
            An :class:`ExtractionResult` with all compliance key points.
        """
        start = time.monotonic()
        entities = []

        for seg in batch.segments:
            mentions = _extract_mentions(seg.text)
            if not mentions:
                continue

            # Scale confidence with number of unique terms found
            term_count = len(mentions)
            confidence = min(
                self.min_confidence + (term_count - 1) * 0.05,
                self.max_confidence,
            )

            # Build a human-readable summary
            terms_str = ", ".join(mentions[:5])
            if len(mentions) > 5:
                terms_str += f" (+{len(mentions) - 5} more)"

            speaker_label = f"{seg.speaker}: " if seg.speaker else ""
            summary = (
                f"Compliance mention — {terms_str}. "
                f'{speaker_label}"{seg.text[:120].rstrip()}{"…" if len(seg.text) > 120 else ""}"'
            )

            entity = make_key_point(
                batch,
                summary=summary,
                speaker=seg.speaker,
                topic="compliance",
                importance="high" if term_count >= 3 else "medium",
                source_segment_id=seg.segment_id,
                confidence=confidence,
            )
            entities.append(entity)

        return self.timed_result(batch, entities, start)


# ---------------------------------------------------------------------------
# Decorator-style variant (demonstrates the @extractor decorator)
# ---------------------------------------------------------------------------

# The decorator approach is useful when you want a quick one-off extractor
# without creating a full class.

from kutana_core.extraction.sdk import extractor  # noqa: E402


@extractor(name="compliance-regex-only", entity_types=["key_point"])
async def regex_compliance_extractor(batch: TranscriptBatch) -> ExtractionResult:
    """Lightweight decorator-based compliance extractor (regulations only).

    Unlike :class:`ComplianceExtractor`, this variant only matches regulation
    names (GDPR, HIPAA, etc.) and skips the broader keyword list.  It is
    suitable for use cases where you want lower false-positive rates.

    Args:
        batch: The windowed transcript batch to process.

    Returns:
        An :class:`ExtractionResult` with key_point entities for regulation
        name mentions.
    """
    from kutana_core.extraction.sdk import make_key_point

    start = time.monotonic()
    entities = []

    for seg in batch.segments:
        regs = _REGULATION_RE.findall(seg.text)
        if not regs:
            continue

        unique_regs = list(dict.fromkeys(r.upper() for r in regs))
        summary = f"Regulation mentioned: {', '.join(unique_regs)}"
        entity = make_key_point(
            batch,
            summary=summary,
            speaker=seg.speaker,
            topic="compliance",
            importance="high",
            source_segment_id=seg.segment_id,
            confidence=0.92,
        )
        entities.append(entity)

    elapsed_ms = (time.monotonic() - start) * 1000.0
    return ExtractionResult(
        batch_id=batch.batch_id,
        entities=entities,
        processing_time_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Programmatic registration helper (optional convenience)
# ---------------------------------------------------------------------------


def register_all(loader: object) -> None:
    """Register all extractors from this module into *loader*.

    This is a convenience function for packages that want to expose a single
    registration entry point.  Typically called at application startup.

    Args:
        loader: An :class:`~kutana_core.extraction.loader.ExtractorLoader`
            instance to register into.

    Example::

        from kutana_core.extraction.loader import ExtractorLoader
        from examples.custom_extractors.compliance_extractor import register_all

        loader = ExtractorLoader()
        register_all(loader)
    """
    # Use duck-typing so this module doesn't need to import ExtractorLoader
    loader.register(ComplianceExtractor)  # type: ignore[union-attr]
    loader.register(regex_compliance_extractor)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Ensure Extractor ABC is properly implemented (type checker aid)
# ---------------------------------------------------------------------------

_: Extractor = ComplianceExtractor()
