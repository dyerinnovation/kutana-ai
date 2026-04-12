"""LiveKitAgentWorker — bot participant in a LiveKit room."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from livekit import api, rtc

from kutana_providers.audio.livekit_adapter import LiveKitAudioAdapter
from kutana_providers.audio.livekit_publisher import LiveKitAudioPublisher

if TYPE_CHECKING:
    from uuid import UUID

    from agent_gateway.audio_bridge import AudioBridge

logger = logging.getLogger(__name__)


class LiveKitAgentWorker:
    """Bot participant in a LiveKit room. One per meeting.

    Connects to the LiveKit room and wires:
    - :class:`LiveKitAudioAdapter` (room audio tracks → STT pipeline)
    - :class:`LiveKitAudioPublisher` (TTS audio → room audio track)

    Args:
        meeting_id: The Kutana meeting UUID this worker belongs to.
        livekit_room_name: Name of the LiveKit room to join.
        livekit_url: WebSocket URL of the LiveKit server.
        livekit_api_key: LiveKit API key for token signing.
        livekit_api_secret: LiveKit API secret for token signing.
        audio_bridge: Shared AudioBridge for pipeline access.
    """

    def __init__(
        self,
        meeting_id: UUID,
        livekit_room_name: str,
        livekit_url: str,
        livekit_api_key: str,
        livekit_api_secret: str,
        audio_bridge: AudioBridge,
    ) -> None:
        self._meeting_id = meeting_id
        self._livekit_room_name = livekit_room_name
        self._livekit_url = livekit_url
        self._livekit_api_key = livekit_api_key
        self._livekit_api_secret = livekit_api_secret
        self._audio_bridge = audio_bridge

        self._room: rtc.Room | None = None
        self._adapter: LiveKitAudioAdapter | None = None
        self._publisher: LiveKitAudioPublisher | None = None
        self._connected: bool = False

    async def connect(self) -> None:
        """Generate JWT, connect to the LiveKit room, start adapter and publisher.

        Creates a bot participant identity, joins the room, then wires up the
        audio adapter (subscribes to remote tracks → STT) and publisher
        (TTS output → local audio track).

        Raises:
            Exception: If room connection or adapter/publisher startup fails.
        """
        token = self._generate_token()

        self._room = rtc.Room()
        await self._room.connect(self._livekit_url, token)
        logger.info(
            "LiveKitAgentWorker connected: meeting=%s room=%s",
            self._meeting_id,
            self._livekit_room_name,
        )

        await self._audio_bridge.ensure_pipeline(self._meeting_id)
        pipeline = self._audio_bridge.get_pipeline(self._meeting_id)

        if pipeline is not None:
            self._adapter = LiveKitAudioAdapter(pipeline=pipeline, room=self._room)
            await self._adapter.start()
        else:
            logger.warning(
                "LiveKitAgentWorker: no pipeline for meeting %s — adapter not started",
                self._meeting_id,
            )

        self._publisher = LiveKitAudioPublisher(room=self._room)
        await self._publisher.start()

        self._connected = True

    async def disconnect(self) -> None:
        """Stop adapter and publisher, then disconnect from the LiveKit room.

        Performs graceful teardown — errors during individual stop steps are
        logged but do not prevent the remaining steps from running.
        """
        self._connected = False

        if self._adapter is not None:
            with contextlib.suppress(Exception):
                await self._adapter.stop()
            self._adapter = None

        if self._publisher is not None:
            with contextlib.suppress(Exception):
                await self._publisher.stop()
            self._publisher = None

        if self._room is not None:
            with contextlib.suppress(Exception):
                await self._room.disconnect()
            self._room = None

        logger.info(
            "LiveKitAgentWorker disconnected: meeting=%s room=%s",
            self._meeting_id,
            self._livekit_room_name,
        )

    @property
    def is_connected(self) -> bool:
        """Whether the worker is currently connected to the LiveKit room."""
        return self._connected

    @property
    def publisher(self) -> LiveKitAudioPublisher | None:
        """The active LiveKitAudioPublisher, or None if not connected."""
        return self._publisher

    def _generate_token(self) -> str:
        """Generate a LiveKit access token for the bot participant.

        Returns:
            A signed JWT granting the bot room_join, can_subscribe, and
            can_publish permissions for the target room.
        """
        identity = f"kutana-gateway-{self._meeting_id}"
        token = (
            api.AccessToken(self._livekit_api_key, self._livekit_api_secret)
            .with_identity(identity)
            .with_name("Kutana AI Gateway")
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=self._livekit_room_name,
                    can_subscribe=True,
                    can_publish=True,
                )
            )
            .to_jwt()
        )
        logger.debug(
            "LiveKitAgentWorker: generated token for identity=%s room=%s",
            identity,
            self._livekit_room_name,
        )
        return token
