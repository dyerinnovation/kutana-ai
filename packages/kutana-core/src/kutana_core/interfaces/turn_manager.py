"""Turn management provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from kutana_core.models.turn import QueueStatus, RaiseHandResult, SpeakingStatus


class TurnManager(ABC):
    """Abstract base class for meeting turn management providers.

    Implementations manage a speaking queue per meeting, supporting
    hand raise / hand lower / speaker advancement. The queue is FIFO
    by default, with optional urgent priority to jump to the front.

    All operations are scoped to a single meeting and are async-safe.
    Implementations should use atomic operations where race conditions
    are possible (e.g., two participants raising hands simultaneously).
    """

    @abstractmethod
    async def raise_hand(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        priority: str = "normal",
        topic: str | None = None,
    ) -> RaiseHandResult:
        """Add a participant to the speaking queue.

        If the participant is already in the queue, returns their current
        position without adding a duplicate. If no one is speaking, the
        participant is immediately promoted to active speaker.

        Args:
            meeting_id: The meeting to raise a hand in.
            participant_id: The participant raising their hand.
            priority: Queue priority — "normal" (FIFO) or "urgent" (front of queue).
            topic: Optional topic the participant wants to discuss.

        Returns:
            RaiseHandResult with queue position and hand raise ID.
            queue_position=0 and was_promoted=True means immediately promoted.
        """
        ...

    @abstractmethod
    async def get_queue_status(self, meeting_id: UUID) -> QueueStatus:
        """Get the current queue state for a meeting.

        Args:
            meeting_id: The meeting to query.

        Returns:
            QueueStatus with active speaker and ordered queue entries.
        """
        ...

    @abstractmethod
    async def get_speaking_status(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> SpeakingStatus:
        """Get the speaking status of a specific participant.

        Args:
            meeting_id: The meeting to query.
            participant_id: The participant to check.

        Returns:
            SpeakingStatus with is_speaking, in_queue, and queue position.
        """
        ...

    @abstractmethod
    async def mark_finished_speaking(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> UUID | None:
        """Mark the active speaker as done and advance to the next in queue.

        If participant_id is not the active speaker, this is a no-op.

        Args:
            meeting_id: The meeting.
            participant_id: The participant finishing their turn.

        Returns:
            UUID of the new active speaker, or None if the queue is empty.
        """
        ...

    @abstractmethod
    async def cancel_hand_raise(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        hand_raise_id: UUID | None = None,
    ) -> bool:
        """Remove a participant from the speaking queue.

        If hand_raise_id is None, cancels the participant's current hand raise.

        Args:
            meeting_id: The meeting.
            participant_id: The participant lowering their hand.
            hand_raise_id: Specific hand raise to cancel (None = cancel current).

        Returns:
            True if an entry was removed, False if the participant was not in queue.
        """
        ...

    @abstractmethod
    async def start_speaking(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> datetime | None:
        """Mark that the active speaker has started actively speaking.

        Transitions the turn state from "your_turn" (promoted, not yet active)
        to "actively_speaking" (speaking has begun). Records the started_at
        timestamp so downstream systems can measure duration and enforce limits.

        This is a no-op if participant_id is not the current active speaker.

        Args:
            meeting_id: The meeting.
            participant_id: The participant who has started speaking.

        Returns:
            UTC datetime when speaking started, or None if not the active speaker.
        """
        ...

    @abstractmethod
    async def set_active_speaker(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> None:
        """Manually set the active speaker, bypassing the queue (host override).

        Args:
            meeting_id: The meeting.
            participant_id: The participant to set as active speaker.
        """
        ...

    @abstractmethod
    async def get_active_speaker(self, meeting_id: UUID) -> UUID | None:
        """Get the current active speaker's participant ID.

        Args:
            meeting_id: The meeting to query.

        Returns:
            UUID of the active speaker, or None if no one is currently speaking.
        """
        ...

    @abstractmethod
    async def clear_meeting(self, meeting_id: UUID) -> None:
        """Clear all turn management state for a meeting.

        Should be called when a meeting ends to release Redis resources.

        Args:
            meeting_id: The meeting to clear.
        """
        ...
