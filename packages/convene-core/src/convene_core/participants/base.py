"""Abstract base classes for meeting participants.

Both human browser users and AI agents are participants. Concrete subclasses
own the connection transport and implement send_event / disconnect for their
specific transport (WebSocket, WebRTC, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4


class Participant(ABC):
    """Abstract base class for a connected meeting participant.

    Attributes:
        id: Unique session identifier (generated at connect time).
        name: Display name of the participant.
        meeting_id: The meeting this participant is connected to.
        participant_type: "human" or "agent".
        capabilities: Set of granted capabilities (speak, listen, transcribe, etc.).
        connected_at: UTC timestamp when the participant connected.
    """

    participant_type: Literal["human", "agent"]

    def __init__(
        self,
        name: str,
        meeting_id: UUID,
        capabilities: set[str],
    ) -> None:
        """Initialise a participant.

        Args:
            name: Display name.
            meeting_id: The meeting being joined.
            capabilities: Granted capability strings.
        """
        self.id: UUID = uuid4()
        self.name = name
        self.meeting_id = meeting_id
        self.capabilities = capabilities
        self.connected_at: datetime = datetime.now(tz=UTC)

    @abstractmethod
    async def send_event(self, event: dict[str, Any]) -> None:
        """Send an event payload to this participant.

        Args:
            event: Event dict to deliver (will be JSON-serialized for transport).
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection resources and notify the participant."""
        ...


class HumanParticipant(Participant):
    """A human user connecting from a browser.

    Humans always receive speak + listen + transcribe capabilities.
    Audio arrives as PCM16 chunks from browser getUserMedia.
    """

    participant_type: Literal["human", "agent"] = "human"

    #: Default capabilities granted to all human participants.
    DEFAULT_CAPABILITIES: frozenset[str] = frozenset({"speak", "listen", "transcribe"})

    def __init__(self, name: str, meeting_id: UUID) -> None:
        """Initialise a human participant with default capabilities.

        Args:
            name: Display name.
            meeting_id: The meeting being joined.
        """
        super().__init__(name, meeting_id, set(self.DEFAULT_CAPABILITIES))


class AgentParticipant(Participant):
    """An AI agent connecting via the agent gateway WebSocket.

    Agent capabilities are configurable via JWT claims and negotiated
    at join time.
    """

    participant_type: Literal["human", "agent"] = "agent"

    def __init__(
        self,
        name: str,
        meeting_id: UUID,
        capabilities: set[str],
    ) -> None:
        """Initialise an agent participant.

        Args:
            name: Display name.
            meeting_id: The meeting being joined.
            capabilities: Negotiated capability strings.
        """
        super().__init__(name, meeting_id, capabilities)
