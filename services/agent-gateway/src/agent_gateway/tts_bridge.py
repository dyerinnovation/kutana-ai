"""TTS synthesis pipeline for text-only agents in the agent gateway.

Responsibilities:
1. Assign distinct voices from a pool to TTS-enabled agents.
2. Enforce per-agent character budgets to cap monthly spend.
3. Cache repeated phrases to avoid redundant API calls.
4. Synthesize text via the configured TTSProvider.
5. Broadcast synthesized audio as ``tts.audio`` events to all participants
   in the meeting that have ``listen`` capability.
"""

from __future__ import annotations

import base64
import contextlib
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from kutana_core.interfaces.tts import TTSProvider, Voice

if TYPE_CHECKING:
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Default voice pool — Cartesia voice IDs (English).
# These are used in round-robin for agents that don't request a specific voice.
_DEFAULT_VOICE_POOL: list[str] = [
    "dbfa416f-d5c3-4006-854b-235ef6bdf4fd",  # Damon - Commanding Narrator
    "d709a7e8-9495-4247-aef0-01b3207d11bf",  # Donny - Steady Presence
    "ea7c252f-6cb1-45f5-8be9-b4f6ac282242",  # Logan - Approachable Friend
    "df872fcd-da17-4b01-a49f-a80d7aaee95e",  # Cameron - Chill Companion
    "db69127a-dbaf-4fa9-b425-2fe67680c348",  # Clint - Rugged Actor
]

_CHAR_BUDGET_DEFAULT: int = 100_000  # characters per agent per session
_CACHE_MAX_SIZE: int = 256  # max number of cached audio entries


# ---------------------------------------------------------------------------
# Voice pool
# ---------------------------------------------------------------------------


class VoicePool:
    """Assigns distinct voices from a fixed pool to agents.

    Agents are assigned the next unused voice in round-robin order.
    If a preferred voice is requested at join time it is used directly
    without consuming a pool slot.

    Attributes:
        _pool: Ordered list of available voice IDs.
        _assignments: Map of session_id -> assigned voice ID.
        _next_index: Rolling counter for round-robin assignment.
    """

    def __init__(self, voice_pool: list[str] | None = None) -> None:
        """Initialise the voice pool.

        Args:
            voice_pool: List of voice IDs to cycle through.
                Defaults to ``_DEFAULT_VOICE_POOL``.
        """
        self._pool: list[str] = list(voice_pool or _DEFAULT_VOICE_POOL)
        self._assignments: dict[UUID, str] = {}
        self._next_index: int = 0

    def assign(self, session_id: UUID, requested_voice: str | None = None) -> str:
        """Assign a voice to a session.

        If the session already has an assignment, return it unchanged.
        If ``requested_voice`` is provided, use it directly.
        Otherwise assign the next pool voice in round-robin order.

        Args:
            session_id: The agent session to assign a voice to.
            requested_voice: Client-requested voice ID (optional).

        Returns:
            The assigned voice ID.
        """
        if session_id in self._assignments:
            return self._assignments[session_id]
        if requested_voice:
            self._assignments[session_id] = requested_voice
            return requested_voice
        voice = self._pool[self._next_index % len(self._pool)]
        self._next_index += 1
        self._assignments[session_id] = voice
        return voice

    def release(self, session_id: UUID) -> None:
        """Remove the voice assignment for a session.

        Args:
            session_id: The session to release.
        """
        self._assignments.pop(session_id, None)

    def get(self, session_id: UUID) -> str | None:
        """Return the voice assigned to a session, or None.

        Args:
            session_id: The session to look up.
        """
        return self._assignments.get(session_id)


# ---------------------------------------------------------------------------
# Character budget tracker
# ---------------------------------------------------------------------------


class CharBudgetTracker:
    """Tracks per-session character usage against a configurable limit.

    Attributes:
        _limit: Maximum characters per session.
        _usage: Map of session_id -> characters consumed.
    """

    def __init__(self, limit: int = _CHAR_BUDGET_DEFAULT) -> None:
        """Initialise the budget tracker.

        Args:
            limit: Character limit per agent session.
        """
        self._limit: int = limit
        self._usage: dict[UUID, int] = {}

    def check_and_consume(self, session_id: UUID, char_count: int) -> bool:
        """Attempt to consume ``char_count`` characters for a session.

        Args:
            session_id: The agent session.
            char_count: Number of characters to consume.

        Returns:
            True if within budget (characters consumed); False if limit exceeded.
        """
        current = self._usage.get(session_id, 0)
        if current + char_count > self._limit:
            return False
        self._usage[session_id] = current + char_count
        return True

    def release(self, session_id: UUID) -> None:
        """Remove the budget record for a session.

        Args:
            session_id: The session to release.
        """
        self._usage.pop(session_id, None)

    def get_usage(self, session_id: UUID) -> int:
        """Return characters consumed for a session.

        Args:
            session_id: The session to query.
        """
        return self._usage.get(session_id, 0)

    @property
    def limit(self) -> int:
        """Return the configured per-session character limit."""
        return self._limit


# ---------------------------------------------------------------------------
# Phrase cache
# ---------------------------------------------------------------------------


class PhraseCache:
    """In-memory LRU-style cache for synthesized audio phrases.

    Keyed on ``(voice_id, text)`` — the same text with a different voice
    is a separate cache entry. Evicts the oldest entry when full.

    Attributes:
        _cache: Ordered dict of cache_key -> audio bytes.
        _max_size: Maximum number of cached entries.
    """

    def __init__(self, max_size: int = _CACHE_MAX_SIZE) -> None:
        """Initialise the phrase cache.

        Args:
            max_size: Maximum number of cached entries.
        """
        self._cache: dict[str, bytes] = {}
        self._max_size: int = max_size

    @staticmethod
    def make_key(voice: str, text: str) -> str:
        """Return the cache key for a voice + text pair.

        Args:
            voice: Voice ID.
            text: Synthesized text.
        """
        return f"{voice}:{text}"

    def get(self, voice: str, text: str) -> bytes | None:
        """Look up cached audio.

        Args:
            voice: Voice ID.
            text: Text that was synthesized.

        Returns:
            Cached audio bytes, or None if not found.
        """
        return self._cache.get(self.make_key(voice, text))

    def put(self, voice: str, text: str, audio: bytes) -> None:
        """Store synthesized audio in the cache.

        Evicts the oldest entry if the cache is full.

        Args:
            voice: Voice ID.
            text: Text that was synthesized.
            audio: Synthesized audio bytes.
        """
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[self.make_key(voice, text)] = audio

    @property
    def size(self) -> int:
        """Return the number of cached entries."""
        return len(self._cache)


# ---------------------------------------------------------------------------
# TTSBridge
# ---------------------------------------------------------------------------


class TTSBridge:
    """Orchestrates TTS synthesis and audio distribution for meetings.

    Acts as the single control point for:
    - Voice assignment (distinct voices per agent).
    - Character budget enforcement (capped spend per agent).
    - Phrase caching (avoid re-synthesizing identical phrases).
    - Synthesis via the configured TTSProvider.
    - Broadcasting synthesized audio to all meeting participants.

    Attributes:
        _provider: The underlying TTS provider.
        _manager: Gateway connection manager (for session broadcast).
        _voice_pool: Assigns distinct voices to agents.
        _budget: Tracks per-session character usage.
        _cache: Caches synthesized audio by (voice, text).
    """

    def __init__(
        self,
        tts_provider: TTSProvider,
        manager: ConnectionManager,
        char_limit: int = _CHAR_BUDGET_DEFAULT,
        voice_pool: list[str] | None = None,
    ) -> None:
        """Initialise the TTS bridge.

        Args:
            tts_provider: The TTS provider to use for synthesis.
            manager: Gateway connection manager for session access.
            char_limit: Per-session character budget (default 100 K).
            voice_pool: Custom voice ID pool; uses default pool if None.
        """
        self._provider = tts_provider
        self._manager = manager
        self._voice_pool = VoicePool(voice_pool)
        self._budget = CharBudgetTracker(limit=char_limit)
        self._cache = PhraseCache()

    # ------------------------------------------------------------------
    # Voice management
    # ------------------------------------------------------------------

    def assign_voice(self, session_id: UUID, requested_voice: str | None = None) -> str:
        """Assign a voice to a session.

        Args:
            session_id: The agent session.
            requested_voice: Client-preferred voice ID (optional).

        Returns:
            Assigned voice ID.
        """
        return self._voice_pool.assign(session_id, requested_voice)

    def get_voice(self, session_id: UUID) -> str | None:
        """Return the voice assigned to a session.

        Args:
            session_id: The session to query.
        """
        return self._voice_pool.get(session_id)

    def release_session(self, session_id: UUID) -> None:
        """Clean up all state for a disconnected session.

        Args:
            session_id: The session to release.
        """
        self._voice_pool.release(session_id)
        self._budget.release(session_id)

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def synthesize_text(
        self,
        session_id: UUID,
        text: str,
        voice: str | None = None,
    ) -> bytes | None:
        """Synthesize text, respecting budget and cache.

        Checks the phrase cache first. If not cached, checks the
        character budget. If within budget, synthesizes via the
        provider and caches the result.

        Args:
            session_id: The requesting agent session (for budget tracking).
            text: Text to synthesize.
            voice: Voice ID to use; falls back to session assignment if None.

        Returns:
            Synthesized audio bytes, or None if budget is exceeded.
        """
        text = text.strip()
        if not text:
            return None

        effective_voice = voice or self._voice_pool.get(session_id) or _DEFAULT_VOICE_POOL[0]

        # Cache hit — no budget consumption for repeated phrases
        cached = self._cache.get(effective_voice, text)
        if cached is not None:
            logger.debug("TTS cache hit for session %s (%d chars)", session_id, len(text))
            return cached

        # Budget check
        if not self._budget.check_and_consume(session_id, len(text)):
            logger.warning(
                "TTS budget exceeded for session %s (%d/%d chars used)",
                session_id,
                self._budget.get_usage(session_id),
                self._budget.limit,
            )
            return None

        # Synthesize
        try:
            audio = await self._provider.synthesize_batch(text, effective_voice)
        except Exception:
            logger.exception(
                "TTS synthesis failed for session %s (voice=%s)", session_id, effective_voice
            )
            return None

        self._cache.put(effective_voice, text, audio)
        logger.debug(
            "TTS synthesized %d chars for session %s (voice=%s, %d bytes)",
            len(text),
            session_id,
            effective_voice,
            len(audio),
        )
        return audio

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def synthesize_and_broadcast(
        self,
        session_id: UUID,
        meeting_id: UUID,
        text: str,
        speaker_name: str,
        voice: str | None = None,
        audio_format: str = "pcm_s16le",
    ) -> bool:
        """Synthesize text and broadcast audio to all meeting listeners.

        Sends a ``tts.audio`` event to every session in the meeting that
        has the ``listen`` capability.

        Args:
            session_id: The speaking agent session.
            meeting_id: The meeting to broadcast to.
            text: Text to synthesize.
            speaker_name: Display name of the speaker (for clients).
            voice: Voice ID override; uses session assignment if None.
            audio_format: Audio format hint for clients (e.g. "wav", "pcm_s16le", "mp3").

        Returns:
            True if synthesis succeeded and audio was broadcast; False otherwise.
        """
        audio = await self.synthesize_text(session_id, text, voice)
        if audio is None:
            return False

        audio_b64 = base64.b64encode(audio).decode()
        payload: dict[str, Any] = {
            "meeting_id": str(meeting_id),
            "speaker_session_id": str(session_id),
            "speaker_name": speaker_name,
            "data": audio_b64,
            "format": audio_format,
            "sample_rate": 24000,  # Cartesia outputs PCM16 @ 24kHz
            "char_count": len(text),
        }

        sessions = self._manager.get_meeting_sessions(meeting_id)
        delivered = 0
        for session in sessions:
            if "listen" not in session.capabilities:
                continue
            try:
                await session.send_event("tts.audio", payload)
                delivered += 1
            except Exception:
                logger.warning("Failed to deliver TTS audio to session %s", session.session_id)

        logger.info(
            "TTS broadcast: meeting=%s speaker=%s chars=%d delivered=%d",
            meeting_id,
            speaker_name,
            len(text),
            delivered,
        )
        return True

    async def synthesize_and_broadcast_stream(
        self,
        session_id: UUID,
        meeting_id: UUID,
        text: str,
        speaker_name: str,
        voice: str | None = None,
        audio_format: str = "pcm_s16le",
    ) -> bool:
        """Stream TTS chunks to meeting listeners as they arrive from the provider.

        Instead of waiting for full synthesis, broadcasts a sequence of events:
        ``tts.audio.stream_start`` -> N x ``tts.audio.chunk`` -> ``tts.audio.stream_end``.
        Clients can begin playback after a small buffer, reducing perceived latency.

        Falls back to batch ``synthesize_and_broadcast`` on provider error.

        Args:
            session_id: The speaking agent session.
            meeting_id: The meeting to broadcast to.
            text: Text to synthesize.
            speaker_name: Display name of the speaker.
            voice: Voice ID override; uses session assignment if None.
            audio_format: Audio format hint for clients.

        Returns:
            True if streaming succeeded; False if budget exceeded or error.
        """
        text = text.strip()
        if not text:
            return False

        effective_voice = voice or self._voice_pool.get(session_id) or _DEFAULT_VOICE_POOL[0]

        # Check cache — if cached, send as single batch (already fast)
        cached = self._cache.get(effective_voice, text)
        if cached is not None:
            return await self.synthesize_and_broadcast(
                session_id, meeting_id, text, speaker_name, voice, audio_format
            )

        # Budget check
        if not self._budget.check_and_consume(session_id, len(text)):
            logger.warning(
                "TTS budget exceeded for session %s (%d/%d chars used)",
                session_id,
                self._budget.get_usage(session_id),
                self._budget.limit,
            )
            return False

        stream_id = str(uuid4())
        sessions = self._manager.get_meeting_sessions(meeting_id)
        listeners = [s for s in sessions if "listen" in s.capabilities]

        # Broadcast stream_start
        start_payload: dict[str, Any] = {
            "stream_id": stream_id,
            "meeting_id": str(meeting_id),
            "speaker_session_id": str(session_id),
            "speaker_name": speaker_name,
            "format": audio_format,
            "sample_rate": 24000,
            "char_count": len(text),
        }
        for session in listeners:
            try:
                await session.send_event("tts.audio.stream_start", start_payload)
            except Exception:
                logger.warning("Failed to send stream_start to %s", session.session_id)

        # Stream chunks from provider
        chunk_index = 0
        all_chunks: list[bytes] = []
        try:
            async for chunk in self._provider.synthesize_stream(text, effective_voice):
                all_chunks.append(chunk)
                chunk_b64 = base64.b64encode(chunk).decode()
                chunk_payload: dict[str, Any] = {
                    "stream_id": stream_id,
                    "chunk_index": chunk_index,
                    "data": chunk_b64,
                }
                for session in listeners:
                    with contextlib.suppress(Exception):  # fire-and-forget per listener
                        await session.send_event("tts.audio.chunk", chunk_payload)
                chunk_index += 1
        except Exception:
            logger.exception(
                "TTS streaming failed for session %s (voice=%s)", session_id, effective_voice
            )
            # Send stream_end with error so clients clean up
            for session in listeners:
                with contextlib.suppress(Exception):
                    await session.send_event(
                        "tts.audio.stream_end",
                        {"stream_id": stream_id, "error": True},
                    )
            return False

        # Cache the complete audio for future requests
        if all_chunks:
            self._cache.put(effective_voice, text, b"".join(all_chunks))

        # Broadcast stream_end
        end_payload: dict[str, Any] = {
            "stream_id": stream_id,
            "total_chunks": chunk_index,
        }
        for session in listeners:
            with contextlib.suppress(Exception):
                await session.send_event("tts.audio.stream_end", end_payload)

        logger.info(
            "TTS stream broadcast: meeting=%s speaker=%s chars=%d chunks=%d listeners=%d",
            meeting_id,
            speaker_name,
            len(text),
            chunk_index,
            len(listeners),
        )
        return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_budget_info(self, session_id: UUID) -> dict[str, int]:
        """Return budget usage info for a session.

        Args:
            session_id: The session to query.

        Returns:
            Dict with ``used``, ``limit``, and ``remaining`` counts.
        """
        used = self._budget.get_usage(session_id)
        return {
            "used": used,
            "limit": self._budget.limit,
            "remaining": max(0, self._budget.limit - used),
        }

    async def list_voices(self) -> list[Voice]:
        """Return the voices available from the configured provider.

        Returns:
            List of Voice objects.
        """
        return await self._provider.list_voices()

    async def close(self) -> None:
        """Close the underlying TTS provider."""
        await self._provider.close()
