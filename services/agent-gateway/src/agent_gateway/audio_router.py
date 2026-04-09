"""Per-meeting audio routing with mixed-minus distribution and VAD."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from agent_gateway.audio_session import AudioSessionHandler

logger = logging.getLogger(__name__)


class AudioRouter:
    """Manages per-meeting audio routing with mixed-minus distribution.

    Each active meeting has one AudioRouter. It:
    - Tracks which audio sessions are connected to the meeting.
    - Distributes incoming audio from each speaker to all other sessions
      (mixed-minus — the sender does not receive their own audio).
    - Monitors speaker activity and auto-stops speakers that have been
      silent for longer than the VAD timeout.

    Attributes:
        meeting_id: The meeting this router serves.
        _sessions: session_id → AudioSessionHandler for all audio sessions.
        _participant_ids: session_id → participant_id string.
        _active_speakers: session_id → monotonic time of last audio frame
            received (only entries for sessions currently in "speaking" state).
        _vad_timeout_s: Silence threshold in seconds before auto-stopping.
        _vad_task: Background asyncio task that polls for silence.
    """

    def __init__(
        self,
        meeting_id: UUID,
        vad_timeout_s: int = 10,
    ) -> None:
        """Initialise the audio router.

        Args:
            meeting_id: The meeting this router belongs to.
            vad_timeout_s: Seconds of silence before a speaker is auto-stopped.
        """
        self.meeting_id = meeting_id
        self._vad_timeout_s = vad_timeout_s
        self._sessions: dict[UUID, AudioSessionHandler] = {}
        self._participant_ids: dict[UUID, str] = {}
        self._active_speakers: dict[UUID, float] = {}  # session_id → last audio monotonic time
        self._vad_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def add_session(
        self,
        session_id: UUID,
        handler: AudioSessionHandler,
        participant_id: str,
    ) -> None:
        """Register an audio session for this meeting.

        Args:
            session_id: The unique session ID.
            handler: The AudioSessionHandler instance.
            participant_id: Stable participant identifier (e.g. agent_config_id).
        """
        self._sessions[session_id] = handler
        self._participant_ids[session_id] = participant_id
        logger.debug(
            "AudioRouter[%s]: added session %s (participant=%s, total=%d)",
            self.meeting_id,
            session_id,
            participant_id,
            len(self._sessions),
        )

    def remove_session(self, session_id: UUID) -> None:
        """Remove an audio session from this meeting.

        Args:
            session_id: The session to remove.
        """
        self._sessions.pop(session_id, None)
        self._participant_ids.pop(session_id, None)
        self._active_speakers.pop(session_id, None)
        logger.debug(
            "AudioRouter[%s]: removed session %s (remaining=%d)",
            self.meeting_id,
            session_id,
            len(self._sessions),
        )

    @property
    def is_empty(self) -> bool:
        """Return True when no audio sessions remain in the meeting."""
        return len(self._sessions) == 0

    # ------------------------------------------------------------------
    # Speaking state
    # ------------------------------------------------------------------

    def set_speaking(self, session_id: UUID, *, speaking: bool) -> None:
        """Mark a session as speaking or not speaking.

        Args:
            session_id: The session changing state.
            speaking: True to enter speaking state, False to exit.
        """
        if speaking:
            self._active_speakers[session_id] = time.monotonic()
        else:
            self._active_speakers.pop(session_id, None)

    def update_audio_timestamp(self, session_id: UUID) -> None:
        """Refresh the last-audio timestamp for VAD heartbeat.

        Called each time a speaking session sends an audio frame.

        Args:
            session_id: The session that sent audio.
        """
        if session_id in self._active_speakers:
            self._active_speakers[session_id] = time.monotonic()

    # ------------------------------------------------------------------
    # Audio routing
    # ------------------------------------------------------------------

    async def route_audio(
        self,
        sender_session_id: UUID,
        audio_bytes: bytes,
    ) -> None:
        """Distribute audio from one participant to all others (mixed-minus).

        Only routes audio while the sender is in "speaking" state. Updates
        the VAD timestamp so the silence monitor resets its counter.

        Args:
            sender_session_id: The session that produced the audio.
            audio_bytes: Raw PCM16 audio bytes.
        """
        if sender_session_id not in self._active_speakers:
            return  # Not speaking — drop the frame

        sender_participant_id = self._participant_ids.get(sender_session_id)
        if sender_participant_id is None:
            return

        self.update_audio_timestamp(sender_session_id)

        for session_id, handler in self._sessions.items():
            if session_id == sender_session_id:
                continue  # mixed-minus: skip the sender
            await handler.receive_audio(
                audio_bytes=audio_bytes,
                speakers=[sender_participant_id],
            )

    # ------------------------------------------------------------------
    # Speaker-change broadcasts
    # ------------------------------------------------------------------

    async def broadcast_speaker_changed(
        self,
        source_session_id: UUID,
        participant_id: str,
        action: str,
    ) -> None:
        """Broadcast a speaker_changed event to all sessions in the meeting.

        Args:
            source_session_id: The session that triggered the change.
            participant_id: The participant whose speaking state changed.
            action: "started" or "stopped".
        """
        for handler in self._sessions.values():
            await handler.send_speaker_changed(
                participant_id=participant_id,
                action=action,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the VAD background monitor task."""
        if self._vad_task is None or self._vad_task.done():
            self._vad_task = asyncio.create_task(
                self._vad_monitor(),
                name=f"vad-monitor-{self.meeting_id}",
            )
            logger.debug("AudioRouter[%s]: VAD monitor started", self.meeting_id)

    async def stop(self) -> None:
        """Stop the VAD monitor and release resources."""
        if self._vad_task is not None and not self._vad_task.done():
            self._vad_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._vad_task
            self._vad_task = None
        logger.debug("AudioRouter[%s]: stopped", self.meeting_id)

    # ------------------------------------------------------------------
    # VAD monitor
    # ------------------------------------------------------------------

    async def _vad_monitor(self) -> None:
        """Background task: auto-stop speakers that have gone silent."""
        try:
            while True:
                await asyncio.sleep(1.0)
                await self._check_vad()
        except asyncio.CancelledError:
            pass

    async def _check_vad(self) -> None:
        """Check all active speakers for silence timeout."""
        now = time.monotonic()
        timed_out = [
            session_id
            for session_id, last_time in list(self._active_speakers.items())
            if now - last_time >= self._vad_timeout_s
        ]
        for session_id in timed_out:
            # Remove from active speakers first to avoid re-triggering
            self._active_speakers.pop(session_id, None)

            handler = self._sessions.get(session_id)
            participant_id = self._participant_ids.get(session_id)
            if handler is None or participant_id is None:
                continue

            logger.info(
                "AudioRouter[%s]: VAD silence timeout for session %s (participant=%s)",
                self.meeting_id,
                session_id,
                participant_id,
            )
            await handler.on_vad_silence_timeout()
            # Notify all sessions that this speaker stopped
            await self.broadcast_speaker_changed(
                source_session_id=session_id,
                participant_id=participant_id,
                action="stopped",
            )
