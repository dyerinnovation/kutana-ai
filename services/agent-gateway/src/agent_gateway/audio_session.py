"""Per-agent audio WebSocket session for the /audio/connect sidecar."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from fastapi import WebSocket

    from agent_gateway.audio_router import AudioRouter
    from agent_gateway.auth import AgentIdentity

logger = logging.getLogger(__name__)

# Audio frames are delivered as fast as the client sends them.
# A bounded outbound queue prevents memory growth if the client is slow.
_OUTBOUND_QUEUE_MAX = 200

# PCM16 LE 16kHz mono, 20ms frame = 16000 * 2 bytes * 0.020 = 640 bytes
_SILENCE_FRAME_BYTES = b"\x00" * 640
_FRAME_INTERVAL_S = 0.020  # 20ms


class AudioSessionHandler:
    """Manages a single /audio/connect WebSocket connection.

    Runs two concurrent loops:
    - Inbound loop: reads messages from the client (audio_data, start_speaking,
      stop_speaking, ping) and dispatches them.
    - Outbound loop: drains the outbound queue and writes messages to the
      client (mixed_audio, speaker_changed, audio_session_joined, pong, error).

    Attributes:
        session_id: Unique ID for this audio session.
        meeting_id: The meeting this session is connected to.
        participant_id: Stable participant identifier (agent_config_id as str).
        audio_format: Negotiated audio format ("pcm16" or "opus").
        is_speaking: Whether this session is currently in speaking state.
        control_session_id: Session ID of the linked control-plane session
            (the /agent/connect WebSocket), if known.
    """

    def __init__(
        self,
        websocket: WebSocket,
        identity: AgentIdentity,
        meeting_id: UUID,
        audio_router: AudioRouter,
        audio_format: str = "pcm16",
        control_session_id: UUID | None = None,
    ) -> None:
        """Initialise the audio session handler.

        Args:
            websocket: The incoming audio WebSocket connection.
            identity: Validated identity from the audio JWT.
            meeting_id: Meeting this audio session is for.
            audio_router: Per-meeting AudioRouter managing distribution.
            audio_format: Negotiated format ("pcm16" default, "opus" optional).
            control_session_id: Linked control-plane session ID (optional).
        """
        self._ws = websocket
        self._identity = identity
        self._router = audio_router
        self.session_id: UUID = uuid4()
        self.meeting_id = meeting_id
        self.participant_id = str(identity.agent_config_id)
        self.audio_format = audio_format
        self.control_session_id = control_session_id
        self.is_speaking = False
        self._outbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=_OUTBOUND_QUEUE_MAX
        )
        self._received_audio_this_tick = False  # Reset each 20ms tick

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def handle(self) -> None:
        """Accept the session, register with the router, and run message loops.

        Runs until the WebSocket closes or an unrecoverable error occurs.
        """
        # Register with the meeting's audio router
        self._router.add_session(
            session_id=self.session_id,
            handler=self,
            participant_id=self.participant_id,
        )
        logger.info(
            "Audio session %s connected (meeting=%s, participant=%s, format=%s)",
            self.session_id,
            self.meeting_id,
            self.participant_id,
            self.audio_format,
        )

        # Confirm the session to the client immediately
        await self._send_direct(
            {
                "type": "audio_session_joined",
                "session_id": str(self.session_id),
                "meeting_id": str(self.meeting_id),
                "format": self.audio_format,
            }
        )

        # Run inbound + outbound + silence-clock loops concurrently.
        # The outbound/clock tasks are cancelled when inbound exits.
        outbound_task = asyncio.create_task(
            self._outbound_loop(),
            name=f"audio-outbound-{self.session_id}",
        )
        silence_task = asyncio.create_task(
            self._silence_clock(),
            name=f"audio-silence-{self.session_id}",
        )
        try:
            await self._inbound_loop()
        except Exception as exc:
            logger.debug(
                "Audio session %s inbound ended: %s",
                self.session_id,
                type(exc).__name__,
            )
        finally:
            outbound_task.cancel()
            silence_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await outbound_task
            with contextlib.suppress(asyncio.CancelledError):
                await silence_task
            # Drain any messages that were enqueued but not yet sent
            await self._drain_outbound()
            await self._cleanup()

    # ------------------------------------------------------------------
    # Inbound (client → server)
    # ------------------------------------------------------------------

    async def _inbound_loop(self) -> None:
        """Read and dispatch messages from the WebSocket until it closes."""
        while True:
            raw = await self._ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await self._send_error("invalid_json", "Message must be valid JSON")
                continue
            await self._dispatch(data)

    async def _dispatch(self, data: dict[str, Any]) -> None:
        """Route an inbound message to the appropriate handler.

        Args:
            data: Parsed JSON message dict from the client.
        """
        msg_type = data.get("type")
        if msg_type == "audio_data":
            await self._handle_audio_data(data)
        elif msg_type == "start_speaking":
            await self._handle_start_speaking()
        elif msg_type == "stop_speaking":
            await self._handle_stop_speaking()
        elif msg_type == "ping":
            await self._enqueue({"type": "pong"})
        else:
            await self._send_error("unknown_type", f"Unknown audio message type: {msg_type!r}")

    async def _handle_audio_data(self, data: dict[str, Any]) -> None:
        """Handle an audio_data frame from the client.

        Validates base64 encoding and forwards to the router for
        mixed-minus distribution to other sessions.

        Args:
            data: Raw parsed audio_data message.
        """
        if not self.is_speaking:
            # Silently drop — the client should call start_speaking first
            return

        raw_b64: str = data.get("data", "")
        if not raw_b64:
            return

        try:
            audio_bytes = base64.b64decode(raw_b64)
        except Exception:
            await self._send_error("invalid_audio", "audio data must be valid base64")
            return

        await self._router.route_audio(self.session_id, audio_bytes)

    async def _handle_start_speaking(self) -> None:
        """Handle start_speaking from the client.

        Transitions the session into speaking state and broadcasts a
        speaker_changed(started) event to all other sessions in the meeting.
        """
        if self.is_speaking:
            return  # Already speaking — idempotent
        self.is_speaking = True
        self._router.set_speaking(self.session_id, speaking=True)
        await self._router.broadcast_speaker_changed(
            source_session_id=self.session_id,
            participant_id=self.participant_id,
            action="started",
        )
        logger.debug("Audio session %s: start_speaking", self.session_id)

    async def _handle_stop_speaking(self) -> None:
        """Handle stop_speaking from the client.

        Transitions the session out of speaking state and broadcasts a
        speaker_changed(stopped) event.
        """
        if not self.is_speaking:
            return  # Not speaking — idempotent
        self.is_speaking = False
        self._router.set_speaking(self.session_id, speaking=False)
        await self._router.broadcast_speaker_changed(
            source_session_id=self.session_id,
            participant_id=self.participant_id,
            action="stopped",
        )
        logger.debug("Audio session %s: stop_speaking", self.session_id)

    # ------------------------------------------------------------------
    # Outbound (server → client)
    # ------------------------------------------------------------------

    async def _outbound_loop(self) -> None:
        """Drain the outbound queue and write messages to the WebSocket."""
        while True:
            msg = await self._outbound_queue.get()
            try:
                await self._ws.send_json(msg)
            except Exception:
                logger.debug(
                    "Audio session %s: outbound write failed, closing",
                    self.session_id,
                )
                break

    def _enqueue_nowait(self, msg: dict[str, Any]) -> None:
        """Enqueue a message, dropping it silently if the queue is full.

        Args:
            msg: Message to enqueue.
        """
        try:
            self._outbound_queue.put_nowait(msg)
        except asyncio.QueueFull:
            logger.debug(
                "Audio session %s outbound queue full — dropping frame",
                self.session_id,
            )

    async def _enqueue(self, msg: dict[str, Any]) -> None:
        """Enqueue a message, dropping if the queue is full (non-blocking).

        Args:
            msg: Message to enqueue.
        """
        self._enqueue_nowait(msg)

    async def _send_direct(self, data: dict[str, Any]) -> None:
        """Send a JSON message directly (bypassing the outbound queue).

        Only safe to call before the outbound loop is started or after it stops.

        Args:
            data: Message dict.
        """
        try:
            await self._ws.send_json(data)
        except Exception:
            logger.debug("Audio session %s: direct send failed", self.session_id)

    async def _drain_outbound(self) -> None:
        """Drain all remaining outbound messages after the loop is cancelled."""
        while not self._outbound_queue.empty():
            msg = self._outbound_queue.get_nowait()
            try:
                await self._ws.send_json(msg)
            except Exception:
                break

    async def _send_error(self, code: str, message: str) -> None:
        """Enqueue an error message to the client.

        Args:
            code: Machine-readable error code.
            message: Human-readable error description.
        """
        await self._enqueue({"type": "error", "code": code, "message": message})

    # ------------------------------------------------------------------
    # Silence clock — continuous 20ms streaming
    # ------------------------------------------------------------------

    async def _silence_clock(self) -> None:
        """Send continuous 20ms audio frames to the agent.

        Every 20ms, if no mixed audio was received from the router
        during this tick, enqueue a silence frame (640 zero bytes).
        This provides a constant audio clock for voice agents that
        need a steady stream of input frames.
        """
        try:
            while True:
                await asyncio.sleep(_FRAME_INTERVAL_S)
                if not self._received_audio_this_tick:
                    self._enqueue_nowait(
                        {
                            "type": "mixed_audio",
                            "data": base64.b64encode(_SILENCE_FRAME_BYTES).decode(),
                            "speakers": [],
                        }
                    )
                self._received_audio_this_tick = False
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Callbacks from AudioRouter
    # ------------------------------------------------------------------

    async def receive_audio(
        self,
        audio_bytes: bytes,
        speakers: list[str],
    ) -> None:
        """Called by the router to deliver mixed audio to this session.

        Enqueues a mixed_audio frame. Frames are dropped when the outbound
        queue is full (backpressure protection). Sets the received flag so
        the silence clock skips this tick.

        Args:
            audio_bytes: PCM16 audio bytes from another participant.
            speakers: Participant IDs whose audio is included in this frame.
        """
        self._received_audio_this_tick = True
        self._enqueue_nowait(
            {
                "type": "mixed_audio",
                "data": base64.b64encode(audio_bytes).decode(),
                "speakers": speakers,
            }
        )

    async def send_speaker_changed(
        self,
        participant_id: str,
        action: str,
    ) -> None:
        """Called by the router to deliver a speaker_changed event.

        Args:
            participant_id: The participant whose speaking state changed.
            action: "started" or "stopped".
        """
        self._enqueue_nowait(
            {
                "type": "speaker_changed",
                "participant_id": participant_id,
                "action": action,
            }
        )

    async def on_vad_silence_timeout(self) -> None:
        """Called by the router when VAD detects this session has gone silent.

        Clears the local speaking flag without re-broadcasting (the router
        handles the broadcast after calling this callback).
        """
        if self.is_speaking:
            self.is_speaking = False
            # Router already removed us from active_speakers; just clear local flag
            logger.info(
                "Audio session %s: VAD silence timeout — auto-stopped speaking",
                self.session_id,
            )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def _cleanup(self) -> None:
        """Clean up state when the session disconnects."""
        if self.is_speaking:
            self.is_speaking = False
            self._router.set_speaking(self.session_id, speaking=False)
            await self._router.broadcast_speaker_changed(
                source_session_id=self.session_id,
                participant_id=self.participant_id,
                action="stopped",
            )
        self._router.remove_session(self.session_id)
        logger.info(
            "Audio session %s disconnected (meeting=%s)",
            self.session_id,
            self.meeting_id,
        )
