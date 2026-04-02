"""Turn management bridge for the agent gateway.

Wraps a TurnManager, broadcasts queue/speaker events to all participants
in a meeting, and runs a background task for auto-advancing the speaker
when the configurable timeout expires.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from kutana_core.interfaces.turn_manager import TurnManager
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# How often the timeout monitor checks for expired speakers (seconds).
_MONITOR_INTERVAL: float = 15.0


class TurnBridge:
    """Bridges the TurnManager and gateway connection manager.

    Provides high-level methods that:
    1. Call the TurnManager for state changes.
    2. Broadcast turn events to all participants in the meeting.
    3. Run a background asyncio task for auto-advance on timeout.

    Attributes:
        turn_manager: The underlying TurnManager provider.
        manager: The gateway's ConnectionManager for session access.
        speaker_timeout_seconds: Seconds before auto-advancing speaker.
    """

    def __init__(
        self,
        turn_manager: TurnManager,
        manager: ConnectionManager,
        speaker_timeout_seconds: int = 300,
    ) -> None:
        """Initialise the turn bridge.

        Args:
            turn_manager: The turn management provider.
            manager: The gateway connection manager.
            speaker_timeout_seconds: Speaker timeout in seconds (default 300 / 5 min).
        """
        self.turn_manager = turn_manager
        self.manager = manager
        self.speaker_timeout_seconds = speaker_timeout_seconds
        self._monitor_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background speaker-timeout monitor."""
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(
                self._monitor_loop(),
                name="turn-bridge-monitor",
            )
            logger.info(
                "TurnBridge monitor started (timeout=%ds)", self.speaker_timeout_seconds
            )

    async def stop(self) -> None:
        """Stop the background monitor and close the TurnManager."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        if hasattr(self.turn_manager, "close"):
            await self.turn_manager.close()  # type: ignore[attr-defined]
        logger.info("TurnBridge stopped")

    # ------------------------------------------------------------------
    # Action handlers — called from session dispatch
    # ------------------------------------------------------------------

    async def handle_raise_hand(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        priority: str = "normal",
        topic: str | None = None,
    ) -> None:
        """Process a raise_hand request and broadcast the result.

        Args:
            meeting_id: The meeting.
            participant_id: The participant raising their hand.
            priority: "normal" or "urgent".
            topic: Optional topic.
        """
        result = await self.turn_manager.raise_hand(
            meeting_id, participant_id, priority=priority, topic=topic
        )

        # Broadcast hand_raised event to all participants
        hand_raised_payload: dict[str, Any] = {
            "meeting_id": str(meeting_id),
            "participant_id": str(participant_id),
            "hand_raise_id": str(result.hand_raise_id),
            "queue_position": result.queue_position,
            "priority": priority,
            "topic": topic,
        }
        await self._broadcast_event(meeting_id, "turn.hand.raised", hand_raised_payload)

        if result.was_promoted:
            # Immediately became active speaker
            await self._broadcast_speaker_changed(
                meeting_id,
                previous_speaker_id=None,
                new_speaker_id=participant_id,
            )
            await self._send_your_turn(meeting_id, participant_id)

        # Always broadcast updated queue
        await self._broadcast_queue_updated(meeting_id)

    async def handle_lower_hand(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        hand_raise_id: UUID | None = None,
    ) -> None:
        """Process a lower_hand request and broadcast the result.

        Args:
            meeting_id: The meeting.
            participant_id: The participant lowering their hand.
            hand_raise_id: Specific raise to cancel (None = current).
        """
        removed = await self.turn_manager.cancel_hand_raise(
            meeting_id, participant_id, hand_raise_id=hand_raise_id
        )
        if removed:
            await self._broadcast_queue_updated(meeting_id)

    async def handle_finished_speaking(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> None:
        """Process a finished_speaking request and broadcast the result.

        Args:
            meeting_id: The meeting.
            participant_id: The participant finishing their turn.
        """
        previous_speaker_id = participant_id
        new_speaker_id = await self.turn_manager.mark_finished_speaking(
            meeting_id, participant_id
        )

        # Broadcast finished event
        await self._broadcast_event(
            meeting_id,
            "turn.speaker.finished",
            {
                "meeting_id": str(meeting_id),
                "participant_id": str(participant_id),
            },
        )

        # Broadcast speaker changed
        await self._broadcast_speaker_changed(
            meeting_id,
            previous_speaker_id=previous_speaker_id,
            new_speaker_id=new_speaker_id,
        )

        # Notify new speaker
        if new_speaker_id is not None:
            await self._send_your_turn(meeting_id, new_speaker_id)

        # Broadcast updated queue
        await self._broadcast_queue_updated(meeting_id)

    async def handle_start_speaking(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> None:
        """Process a start_speaking signal and broadcast to all participants.

        Args:
            meeting_id: The meeting.
            participant_id: The participant who has started speaking.
        """
        started_at = await self.turn_manager.start_speaking(meeting_id, participant_id)  # type: ignore[attr-defined]
        if started_at is None:
            # Participant is not the active speaker — no-op
            return

        await self._broadcast_event(
            meeting_id,
            "turn.speaking.started",
            {
                "meeting_id": str(meeting_id),
                "participant_id": str(participant_id),
                "started_at": started_at.isoformat(),
            },
        )

    async def handle_set_speaker(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> None:
        """Process a host set_speaker override and broadcast the result.

        Args:
            meeting_id: The meeting.
            participant_id: The participant to set as speaker.
        """
        previous_id = await self.turn_manager.get_active_speaker(meeting_id)
        await self.turn_manager.set_active_speaker(meeting_id, participant_id)
        await self._broadcast_speaker_changed(
            meeting_id,
            previous_speaker_id=previous_id,
            new_speaker_id=participant_id,
        )
        await self._send_your_turn(meeting_id, participant_id)
        await self._broadcast_queue_updated(meeting_id)

    async def get_queue_payload(self, meeting_id: UUID) -> dict[str, Any]:
        """Return a serializable queue status dict.

        Args:
            meeting_id: The meeting to query.

        Returns:
            Dict with active_speaker_id and queue list.
        """
        status = await self.turn_manager.get_queue_status(meeting_id)
        return {
            "meeting_id": str(meeting_id),
            "active_speaker_id": str(status.active_speaker_id) if status.active_speaker_id else None,
            "queue": [
                {
                    "position": entry.position,
                    "participant_id": str(entry.participant_id),
                    "hand_raise_id": str(entry.hand_raise_id),
                    "priority": entry.priority,
                    "topic": entry.topic,
                    "raised_at": entry.raised_at.isoformat(),
                }
                for entry in status.queue
            ],
        }

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    async def _broadcast_event(
        self,
        meeting_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send an event to all sessions in the meeting.

        Args:
            meeting_id: The meeting to broadcast to.
            event_type: Event type string.
            payload: Event payload.
        """
        sessions = self.manager.get_meeting_sessions(meeting_id)
        for session in sessions:
            try:
                await session.send_event(event_type, payload)
            except Exception:
                logger.warning(
                    "Failed to send %s to session %s",
                    event_type,
                    session.session_id,
                )

    async def _broadcast_speaker_changed(
        self,
        meeting_id: UUID,
        previous_speaker_id: UUID | None,
        new_speaker_id: UUID | None,
    ) -> None:
        """Broadcast a speaker_changed event to all participants.

        Args:
            meeting_id: The meeting.
            previous_speaker_id: Outgoing speaker.
            new_speaker_id: Incoming speaker.
        """
        await self._broadcast_event(
            meeting_id,
            "turn.speaker.changed",
            {
                "meeting_id": str(meeting_id),
                "previous_speaker_id": str(previous_speaker_id) if previous_speaker_id else None,
                "new_speaker_id": str(new_speaker_id) if new_speaker_id else None,
            },
        )

    async def _broadcast_queue_updated(self, meeting_id: UUID) -> None:
        """Broadcast the current queue state to all participants.

        Args:
            meeting_id: The meeting.
        """
        payload = await self.get_queue_payload(meeting_id)
        await self._broadcast_event(meeting_id, "turn.queue.updated", payload)

    async def _send_your_turn(self, meeting_id: UUID, participant_id: UUID) -> None:
        """Send a targeted your_turn notification to a specific participant.

        Iterates sessions looking for a session belonging to participant_id.

        Args:
            meeting_id: The meeting.
            participant_id: The participant to notify.
        """
        sessions = self.manager.get_meeting_sessions(meeting_id)
        for session in sessions:
            try:
                # Both agent and human sessions store identity.agent_config_id
                session_pid = session._identity.agent_config_id  # type: ignore[attr-defined]
                if session_pid == participant_id:
                    await session.send_event(
                        "turn.your_turn",
                        {"meeting_id": str(meeting_id)},
                    )
                    break
            except Exception:
                logger.warning(
                    "Failed to send your_turn to session %s",
                    session.session_id,
                )

    # ------------------------------------------------------------------
    # Background monitor
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Background task: auto-advance speaker on timeout.

        Polls active meetings every _MONITOR_INTERVAL seconds and advances
        the speaker if they have exceeded speaker_timeout_seconds.
        """
        while True:
            try:
                await asyncio.sleep(_MONITOR_INTERVAL)
                await self._check_timeouts()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in turn monitor loop")

    async def _check_timeouts(self) -> None:
        """Check all active meetings for speaker timeout violations."""
        # Only check meetings that have active WebSocket sessions
        active_meeting_ids = list(self.manager._meeting_sessions.keys())

        for meeting_id in active_meeting_ids:
            try:
                elapsed = await self.turn_manager.get_speaker_elapsed_seconds(meeting_id)  # type: ignore[attr-defined]
                if elapsed is not None and elapsed > self.speaker_timeout_seconds:
                    current_speaker = await self.turn_manager.get_active_speaker(meeting_id)
                    if current_speaker is not None:
                        logger.info(
                            "Speaker timeout: advancing from %s in meeting %s (%.0fs elapsed)",
                            current_speaker,
                            meeting_id,
                            elapsed,
                        )
                        await self.handle_finished_speaking(meeting_id, current_speaker)
            except Exception:
                logger.warning("Error checking timeout for meeting %s", meeting_id)
