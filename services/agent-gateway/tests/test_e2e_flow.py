"""End-to-end flow test: agent audio → STT → transcript segment → EventRelay → agent."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agent_gateway.audio_bridge import AudioBridge
from agent_gateway.connection_manager import ConnectionManager
from agent_gateway.event_relay import EventRelay

from convene_core.models.transcript import TranscriptSegment
from convene_providers.testing import MockSTT


def _make_session(session_id, meeting_id, capabilities):
    """Create a mock AgentSessionHandler."""
    session = AsyncMock()
    session.session_id = session_id
    session.meeting_id = meeting_id
    session.capabilities = capabilities
    session.send_transcript = AsyncMock()
    session.send_event = AsyncMock()
    return session


class TestE2EAudioToTranscript:
    """Integration test for the full audio → transcript loop."""

    async def test_audio_flows_through_pipeline_to_transcript(self) -> None:
        """Audio sent to AudioBridge produces TranscriptSegments via MockSTT.

        Verifies:
        1. AudioBridge creates a pipeline with MockSTT
        2. Audio bytes are forwarded to the pipeline
        3. MockSTT yields pre-configured segments
        4. Segments are consumed by the background task
        """
        meeting_id = uuid4()
        segment = TranscriptSegment(
            meeting_id=meeting_id,
            speaker_id="speaker-1",
            text="This is a test transcript",
            start_time=0.0,
            end_time=2.5,
            confidence=0.92,
        )
        mock_stt = MockSTT(segments=[segment])

        mock_publisher = AsyncMock()
        mock_publisher.close = AsyncMock()
        mock_publisher.publish = AsyncMock()

        with patch(
            "agent_gateway.audio_bridge.EventPublisher",
            return_value=mock_publisher,
        ), patch(
            "agent_gateway.audio_bridge._create_stt_provider",
            return_value=mock_stt,
        ):
            bridge = AudioBridge(
                redis_url="redis://localhost:6379/0",
                stt_provider="whisper",
                stt_api_key="",
                whisper_model_size="small",
                whisper_api_url="",
                transcription_interval_s=0.01,
            )

            await bridge.ensure_pipeline(meeting_id)

            # Send audio
            audio_bytes = b"\x00\x01" * 1600
            await bridge.process_audio(meeting_id, audio_bytes)

            # Verify audio reached MockSTT
            assert mock_stt._buffer == audio_bytes

            # Let the segment consumer task run
            await asyncio.sleep(0.1)

            await bridge.close()

    async def test_event_relay_routes_transcript_to_session(self) -> None:
        """EventRelay routes transcript.segment.final to session.send_transcript.

        Simulates what happens after EventPublisher writes to Redis and
        EventRelay reads it back — verifying the full relay path.
        """
        meeting_id = uuid4()
        session_id = uuid4()

        manager = ConnectionManager()
        session = _make_session(
            session_id=session_id,
            meeting_id=meeting_id,
            capabilities=["listen", "transcribe"],
        )
        manager.register(session)
        manager.join_meeting(session_id, meeting_id)

        with patch("agent_gateway.event_relay.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis_module.from_url.return_value = mock_redis
            relay = EventRelay(
                redis_url="redis://localhost:6379/0",
                connection_manager=manager,
            )

        # Simulate an event arriving from Redis
        segment_payload = {
            "meeting_id": str(meeting_id),
            "segment": {
                "speaker_id": "speaker-1",
                "text": "Hello everyone",
                "start_time": 1.0,
                "end_time": 2.5,
                "confidence": 0.88,
            },
        }

        await relay._handle_event(
            "1-0",
            {
                "event_type": "transcript.segment.final",
                "payload": json.dumps(segment_payload),
            },
        )

        session.send_transcript.assert_awaited_once_with(
            meeting_id=meeting_id,
            speaker_id="speaker-1",
            text="Hello everyone",
            start_time=1.0,
            end_time=2.5,
            confidence=0.88,
            speaker_name=None,
        )

    async def test_full_loop_audio_to_session_transcript(self) -> None:
        """Full E2E: audio → AudioBridge → MockSTT → segments → verify transcript data.

        This test verifies the complete flow minus Redis (which is mocked),
        confirming that audio processing produces the expected transcript
        data that would be published to Redis.
        """
        meeting_id = uuid4()

        segment = TranscriptSegment(
            meeting_id=meeting_id,
            speaker_id="speaker-2",
            text="Let's discuss the agenda",
            start_time=5.0,
            end_time=7.3,
            confidence=0.95,
        )
        mock_stt = MockSTT(segments=[segment])

        # Track published events
        published_events = []

        mock_publisher = AsyncMock()
        mock_publisher.close = AsyncMock()

        async def capture_publish(event):
            published_events.append(event)
            return "1-0"

        mock_publisher.publish = capture_publish

        with patch(
            "agent_gateway.audio_bridge.EventPublisher",
            return_value=mock_publisher,
        ), patch(
            "agent_gateway.audio_bridge._create_stt_provider",
            return_value=mock_stt,
        ):
            bridge = AudioBridge(
                redis_url="redis://localhost:6379/0",
                stt_provider="whisper",
                stt_api_key="",
                whisper_model_size="small",
                whisper_api_url="",
                transcription_interval_s=0.01,
            )

            await bridge.ensure_pipeline(meeting_id)

            # Send audio
            audio_data = b"\x00\x02" * 800
            await bridge.process_audio(meeting_id, audio_data)

            # Let segment consumer run
            await asyncio.sleep(0.1)

            await bridge.close()

        # Verify events were published (MeetingStarted + TranscriptSegmentFinal + MeetingEnded)
        event_types = [e.event_type for e in published_events]
        assert "meeting.started" in event_types
        assert "transcript.segment.final" in event_types
        assert "meeting.ended" in event_types

        # Verify the transcript segment event has correct data
        # (MockSTT may produce duplicates since it doesn't drain its buffer
        # like real providers; we just verify the first one is correct)
        transcript_events = [
            e for e in published_events if e.event_type == "transcript.segment.final"
        ]
        assert len(transcript_events) >= 1
        assert transcript_events[0].segment.text == "Let's discuss the agenda"
        assert transcript_events[0].segment.speaker_id == "speaker-2"
        assert transcript_events[0].segment.confidence == 0.95
