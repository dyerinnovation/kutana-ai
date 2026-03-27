"""Input sanitization and validation for all MCP tool parameters.

Validates types, lengths, and allowed values. Raises ValueError with a
descriptive message on any violation — callers should catch and return
a JSON error string.

Rules enforced:
    meeting_id      — valid UUID format (36-char hyphenated)
    content         — max 2 000 chars, HTML/script tags stripped,
                      control characters removed
    priority        — must be "normal" or "urgent"
    topic           — max 200 chars, control characters removed
    description     — max 200 chars, control characters removed
    channel         — max 64 chars, alphanumeric + hyphens/underscores
    last_n          — integer, clamped 1–500
    limit           — integer, clamped 1–200
"""

from __future__ import annotations

import re
from uuid import UUID

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Matches any HTML / XML tag (including <script>, <img onerror=...>, etc.)
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.IGNORECASE | re.DOTALL)

# Control characters excluding tab (\x09), newline (\x0a), carriage return (\x0d)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Prompt-injection patterns commonly used to hijack LLM context
_INJECTION_PATTERN_RE = re.compile(
    r"(system\s*:|<\s*/?system\s*>|<\s*/?instructions?\s*>|"
    r"ignore\s+previous\s+instructions?|"
    r"\[INST\]|\[/INST\]|###\s*Instruction)",
    re.IGNORECASE,
)

# Valid channel name: alphanumeric, hyphens, underscores (no whitespace)
_CHANNEL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_CONTENT_LENGTH = 2_000
MAX_CONTEXT_LENGTH = 5_000
MAX_TOPIC_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 200
MAX_CHANNEL_NAME_LENGTH = 64
MAX_TITLE_LENGTH = 200


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_meeting_id(meeting_id: str) -> UUID:
    """Parse and validate *meeting_id* as a UUID.

    Args:
        meeting_id: Raw string from the tool parameter.

    Returns:
        Parsed UUID object.

    Raises:
        ValueError: If not a valid UUID.
    """
    try:
        return UUID(meeting_id)
    except (ValueError, AttributeError):
        raise ValueError(
            f"Invalid meeting_id: expected a UUID (e.g. 'xxxxxxxx-xxxx-…'), "
            f"got {meeting_id!r:.50}"
        )


def sanitize_content(content: str) -> str:
    """Sanitize chat message content.

    - Strips HTML / script tags
    - Removes control characters (keeps tab, newline, CR)
    - Strips prompt-injection patterns
    - Enforces max {MAX_CONTENT_LENGTH} characters

    Args:
        content: Raw message content.

    Returns:
        Cleaned content string.

    Raises:
        ValueError: If content exceeds the maximum length after sanitization.
    """
    cleaned = _HTML_TAG_RE.sub("", content)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = _INJECTION_PATTERN_RE.sub("[filtered]", cleaned)

    if len(cleaned) > MAX_CONTENT_LENGTH:
        raise ValueError(
            f"Content too long: max {MAX_CONTENT_LENGTH} characters, "
            f"got {len(cleaned)}"
        )
    return cleaned


def sanitize_context(context: str) -> str:
    """Sanitize meeting context content (allows up to 5000 chars).

    Same cleaning rules as ``sanitize_content`` but with a higher length
    limit, suitable for injecting meeting context blobs.

    Args:
        context: Raw context content.

    Returns:
        Cleaned context string.

    Raises:
        ValueError: If context exceeds the maximum length after sanitization.
    """
    cleaned = _HTML_TAG_RE.sub("", context)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = _INJECTION_PATTERN_RE.sub("[filtered]", cleaned)

    if len(cleaned) > MAX_CONTEXT_LENGTH:
        raise ValueError(
            f"Context too long: max {MAX_CONTEXT_LENGTH} characters, "
            f"got {len(cleaned)}"
        )
    return cleaned


def validate_priority(priority: str) -> str:
    """Validate that *priority* is one of the allowed values.

    Args:
        priority: Raw priority string.

    Returns:
        The validated priority string (unchanged).

    Raises:
        ValueError: If priority is not "normal" or "urgent".
    """
    allowed = {"normal", "urgent"}
    if priority not in allowed:
        raise ValueError(
            f"Invalid priority: must be one of {sorted(allowed)}, "
            f"got {priority!r}"
        )
    return priority


def sanitize_topic(topic: str | None) -> str | None:
    """Sanitize optional topic / description field.

    - Removes control characters
    - Strips prompt-injection patterns
    - Enforces max {MAX_TOPIC_LENGTH} characters

    Args:
        topic: Raw topic string or None.

    Returns:
        Cleaned topic string or None.

    Raises:
        ValueError: If topic exceeds the maximum length.
    """
    if topic is None:
        return None
    cleaned = _CONTROL_CHAR_RE.sub("", topic)
    cleaned = _INJECTION_PATTERN_RE.sub("[filtered]", cleaned)
    if len(cleaned) > MAX_TOPIC_LENGTH:
        raise ValueError(
            f"Topic too long: max {MAX_TOPIC_LENGTH} characters, "
            f"got {len(cleaned)}"
        )
    return cleaned


def sanitize_description(description: str) -> str:
    """Sanitize task description.

    - Removes control characters
    - Strips prompt-injection patterns
    - Enforces max {MAX_DESCRIPTION_LENGTH} characters

    Args:
        description: Raw description string.

    Returns:
        Cleaned description string.

    Raises:
        ValueError: If description exceeds the maximum length.
    """
    cleaned = _CONTROL_CHAR_RE.sub("", description)
    cleaned = _INJECTION_PATTERN_RE.sub("[filtered]", cleaned)
    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(
            f"Description too long: max {MAX_DESCRIPTION_LENGTH} characters, "
            f"got {len(cleaned)}"
        )
    return cleaned


def validate_channel(channel: str) -> str:
    """Validate channel name format.

    Args:
        channel: Raw channel name.

    Returns:
        Validated channel name (unchanged).

    Raises:
        ValueError: If channel name is invalid.
    """
    if not channel or len(channel) > MAX_CHANNEL_NAME_LENGTH:
        raise ValueError(
            f"Channel name must be 1–{MAX_CHANNEL_NAME_LENGTH} characters, "
            f"got {len(channel)!r}"
        )
    if not _CHANNEL_NAME_RE.match(channel):
        raise ValueError(
            f"Channel name must contain only alphanumerics, hyphens, and "
            f"underscores, got {channel!r:.30}"
        )
    return channel


def sanitize_title(title: str) -> str:
    """Sanitize meeting title.

    Args:
        title: Raw title string.

    Returns:
        Cleaned title string.

    Raises:
        ValueError: If title exceeds the maximum length.
    """
    cleaned = _CONTROL_CHAR_RE.sub("", title)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    if len(cleaned) > MAX_TITLE_LENGTH:
        raise ValueError(
            f"Title too long: max {MAX_TITLE_LENGTH} characters, "
            f"got {len(cleaned)}"
        )
    return cleaned


def clamp_last_n(value: int, *, min_val: int = 1, max_val: int = 500) -> int:
    """Clamp last_n to a safe range.

    Args:
        value: Requested count.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Clamped integer.
    """
    return max(min_val, min(value, max_val))


def clamp_limit(value: int, *, min_val: int = 1, max_val: int = 200) -> int:
    """Clamp a limit parameter to a safe range.

    Args:
        value: Requested limit.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Clamped integer.
    """
    return max(min_val, min(value, max_val))
