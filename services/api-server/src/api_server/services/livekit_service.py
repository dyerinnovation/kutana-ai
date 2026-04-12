"""LiveKit server-side service: room provisioning + participant token generation.

This module wraps the ``livekit-api`` SDK for two api-server concerns:

- ``ensure_room`` — idempotently provision a room on the LiveKit server
  (via ``RoomService.create_room``) and return its sid. The api-server
  stores this sid on ``RoomORM.livekit_room_id`` at meeting-start time.
- ``generate_participant_token`` — issue a short-lived JWT the browser/mobile
  client uses to join the LiveKit room as a human participant.

Mirrors the token pattern used by ``agent_gateway.livekit_worker``.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from livekit import api

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class LiveKitService:
    """Server-side LiveKit client for room provisioning and token issuance.

    Args:
        url: LiveKit server URL (ws:// or https://). Used for both REST
            (room provisioning) and returned to clients for WebRTC connect.
        api_key: LiveKit API key for signing tokens and REST auth.
        api_secret: LiveKit API secret for signing tokens and REST auth.
        token_ttl_seconds: Lifetime of participant tokens. Defaults to 6 hours.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
        token_ttl_seconds: int = 21600,
    ) -> None:
        self._url = url
        self._api_key = api_key
        self._api_secret = api_secret
        self._token_ttl_seconds = token_ttl_seconds

    @property
    def url(self) -> str:
        """LiveKit server URL clients should connect to."""
        return self._url

    async def ensure_room(self, room_name: str) -> str:
        """Idempotently create the LiveKit room and return its sid.

        LiveKit's ``create_room`` is idempotent on ``name`` — if a room with
        the same name already exists, the existing room is returned.

        Args:
            room_name: Human-readable room name (reuses ``RoomORM.name``).

        Returns:
            The LiveKit-assigned room sid.

        Raises:
            Exception: If the LiveKit REST call fails.
        """
        lkapi = api.LiveKitAPI(self._url, self._api_key, self._api_secret)
        try:
            room_info = await lkapi.room.create_room(
                api.CreateRoomRequest(name=room_name),
            )
            logger.info(
                "LiveKitService.ensure_room: name=%s sid=%s",
                room_name,
                room_info.sid,
            )
            return room_info.sid
        finally:
            await lkapi.aclose()

    def generate_participant_token(
        self,
        user_id: UUID,
        user_name: str,
        room_name: str,
    ) -> str:
        """Generate a LiveKit JWT for a human participant.

        Args:
            user_id: Kutana user UUID. Used to build the LiveKit identity
                (``human-<uuid>``), which must be unique per participant.
            user_name: Display name shown to other participants in the room.
            room_name: Name of the LiveKit room the token grants access to.

        Returns:
            Signed JWT granting room_join + publish/subscribe/publish_data.
        """
        identity = f"human-{user_id}"
        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(identity)
            .with_name(user_name)
            .with_ttl(timedelta(seconds=self._token_ttl_seconds))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .to_jwt()
        )
        logger.debug(
            "LiveKitService: generated participant token identity=%s room=%s",
            identity,
            room_name,
        )
        return token
