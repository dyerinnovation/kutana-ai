"""Calendar synchronisation for upcoming meetings."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from kutana_core.models.meeting import Meeting, MeetingStatus

logger = logging.getLogger(__name__)


class CalendarSync:
    """Synchronises external calendar events into Kutana meetings.

    Provides a placeholder for calendar API integration (Google
    Calendar, Microsoft Graph, etc.).  The actual API calls will be
    implemented once OAuth credentials and calendar provider
    selection are configured.

    Attributes:
        _session_factory: Async session factory for database access.
    """

    def __init__(
        self,
        session_factory: object,
    ) -> None:
        """Initialise the calendar sync service.

        Args:
            session_factory: SQLAlchemy async session factory (typed as
                object until the database layer is fully wired up).
        """
        self._session_factory = session_factory

    async def sync_upcoming_meetings(self) -> list[Meeting]:
        """Fetch upcoming meetings from the calendar provider.

        This is a placeholder implementation that returns an empty
        list.  A real implementation would:
        1. Authenticate with the calendar provider.
        2. Fetch events for the next 24 hours.
        3. Filter for events with dial-in numbers.
        4. Create or update Meeting records.

        Returns:
            List of Meeting objects synced from the calendar.
        """
        logger.info("Syncing upcoming meetings from calendar")

        # Placeholder: in production, this would call a calendar API
        # and process real events.
        return []

    def create_meeting_from_event(
        self,
        event: dict[str, Any],
    ) -> Meeting:
        """Convert a calendar event dictionary into a Meeting model.

        Extracts dial-in information, scheduled time, and title from
        the calendar event payload.

        Args:
            event: A dictionary representing a calendar event.  Expected
                keys include ``title``, ``dial_in_number``,
                ``meeting_code``, ``platform``, and ``scheduled_at``
                (ISO 8601 string).

        Returns:
            A new Meeting domain model instance.
        """
        scheduled_str = event.get("scheduled_at", "")
        if isinstance(scheduled_str, str) and scheduled_str:
            scheduled_at = datetime.fromisoformat(scheduled_str)
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=UTC)
        else:
            scheduled_at = datetime.now(tz=UTC)

        meeting = Meeting(
            id=uuid4(),
            platform=str(event.get("platform", "unknown")),
            dial_in_number=str(event.get("dial_in_number", "")),
            meeting_code=str(event.get("meeting_code", "")),
            title=event.get("title"),
            scheduled_at=scheduled_at,
            status=MeetingStatus.SCHEDULED,
        )

        logger.info(
            "Created meeting from calendar event: id=%s, title=%s",
            meeting.id,
            meeting.title,
        )
        return meeting
