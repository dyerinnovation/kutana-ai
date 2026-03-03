"""Tests for the AudioBridge component."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agent_gateway.audio_bridge import AudioBridge


@pytest.fixture
def mock_event_publisher():
    """Create a mock EventPublisher."""
    publisher = AsyncMock()
    publisher.close = AsyncMock()
    return publisher


@pytest.fixture
def mock_pipeline():
    """Create a mock AudioPipeline."""
    pipeline = AsyncMock()
    pipeline.process_audio = AsyncMock()
    pipeline.close = AsyncMock()

    async def empty_segments():
        return
        yield  # pragma: no cover — makes this an async generator

    pipeline.get_segments = empty_segments
    return pipeline


@pytest.fixture
def bridge(mock_event_publisher):
    """Create an AudioBridge with mocked EventPublisher and short interval."""
    with patch(
        "agent_gateway.audio_bridge.EventPublisher",
        return_value=mock_event_publisher,
    ):
        return AudioBridge(
            redis_url="redis://localhost:6379/0",
            stt_provider="whisper",
            stt_api_key="",
            whisper_model_size="small",
            whisper_api_url="",
            transcription_interval_s=0.01,
        )


class TestEnsurePipeline:
    """Tests for ensure_pipeline."""

    async def test_creates_pipeline(self, bridge, mock_pipeline) -> None:
        """Creates a pipeline and starts segment consumer task."""
        meeting_id = uuid4()

        with patch(
            "agent_gateway.audio_bridge._create_stt_provider"
        ) as mock_factory, patch(
            "agent_gateway.audio_bridge.AudioPipeline",
            return_value=mock_pipeline,
        ):
            mock_factory.return_value = MagicMock()
            await bridge.ensure_pipeline(meeting_id)

        assert meeting_id in bridge._pipelines
        assert meeting_id in bridge._segment_tasks
        assert not bridge._segment_tasks[meeting_id].done()

        # Cleanup
        await bridge.close()

    async def test_idempotent(self, bridge, mock_pipeline) -> None:
        """Calling ensure_pipeline twice for the same meeting is a no-op."""
        meeting_id = uuid4()

        with patch(
            "agent_gateway.audio_bridge._create_stt_provider"
        ) as mock_factory, patch(
            "agent_gateway.audio_bridge.AudioPipeline",
            return_value=mock_pipeline,
        ) as mock_pipeline_cls:
            mock_factory.return_value = MagicMock()
            await bridge.ensure_pipeline(meeting_id)
            await bridge.ensure_pipeline(meeting_id)

        assert mock_pipeline_cls.call_count == 1

        await bridge.close()

    async def test_multiple_meetings_get_separate_pipelines(
        self, bridge, mock_pipeline
    ) -> None:
        """Each meeting gets its own pipeline instance."""
        m1 = uuid4()
        m2 = uuid4()

        pipelines_created = []

        def make_pipeline(**kwargs):
            p = AsyncMock()
            p.process_audio = AsyncMock()
            p.close = AsyncMock()

            async def empty_segments():
                return
                yield  # pragma: no cover

            p.get_segments = empty_segments
            pipelines_created.append(p)
            return p

        with patch(
            "agent_gateway.audio_bridge._create_stt_provider"
        ) as mock_factory, patch(
            "agent_gateway.audio_bridge.AudioPipeline",
            side_effect=make_pipeline,
        ):
            mock_factory.return_value = MagicMock()
            await bridge.ensure_pipeline(m1)
            await bridge.ensure_pipeline(m2)

        assert len(bridge._pipelines) == 2
        assert bridge._pipelines[m1] is not bridge._pipelines[m2]

        await bridge.close()


class TestProcessAudio:
    """Tests for process_audio."""

    async def test_forwards_bytes_to_pipeline(self, bridge, mock_pipeline) -> None:
        """Audio bytes are forwarded to the meeting's pipeline."""
        meeting_id = uuid4()
        audio = b"\x00\x01" * 800

        with patch(
            "agent_gateway.audio_bridge._create_stt_provider"
        ), patch(
            "agent_gateway.audio_bridge.AudioPipeline",
            return_value=mock_pipeline,
        ):
            await bridge.ensure_pipeline(meeting_id)

        await bridge.process_audio(meeting_id, audio)
        mock_pipeline.process_audio.assert_awaited_once_with(audio)

        await bridge.close()

    async def test_drops_audio_for_unknown_meeting(self, bridge) -> None:
        """Audio for unknown meeting is dropped without error."""
        await bridge.process_audio(uuid4(), b"\x00" * 100)
        # No exception = pass

        await bridge.close()


class TestClosePipeline:
    """Tests for close_pipeline."""

    async def test_closes_pipeline_and_cancels_task(
        self, bridge, mock_pipeline
    ) -> None:
        """Closing a pipeline removes it and cancels the segment task."""
        meeting_id = uuid4()

        with patch(
            "agent_gateway.audio_bridge._create_stt_provider"
        ), patch(
            "agent_gateway.audio_bridge.AudioPipeline",
            return_value=mock_pipeline,
        ):
            await bridge.ensure_pipeline(meeting_id)

        await bridge.close_pipeline(meeting_id)

        assert meeting_id not in bridge._pipelines
        assert meeting_id not in bridge._segment_tasks
        mock_pipeline.close.assert_awaited_once()

        await bridge.close()

    async def test_close_nonexistent_pipeline_is_noop(self, bridge) -> None:
        """Closing a pipeline that doesn't exist is a no-op."""
        await bridge.close_pipeline(uuid4())
        # No exception = pass

        await bridge.close()


class TestClose:
    """Tests for close."""

    async def test_closes_all_pipelines(self, bridge) -> None:
        """close() cleans up all pipelines and the EventPublisher."""
        pipelines = []

        def make_pipeline(**kwargs):
            p = AsyncMock()
            p.process_audio = AsyncMock()
            p.close = AsyncMock()

            async def empty_segments():
                return
                yield  # pragma: no cover

            p.get_segments = empty_segments
            pipelines.append(p)
            return p

        m1, m2 = uuid4(), uuid4()

        with patch(
            "agent_gateway.audio_bridge._create_stt_provider"
        ), patch(
            "agent_gateway.audio_bridge.AudioPipeline",
            side_effect=make_pipeline,
        ):
            await bridge.ensure_pipeline(m1)
            await bridge.ensure_pipeline(m2)

        await bridge.close()

        assert len(bridge._pipelines) == 0
        assert len(bridge._segment_tasks) == 0
        for p in pipelines:
            p.close.assert_awaited_once()
