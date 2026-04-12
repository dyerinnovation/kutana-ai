"""Shared fixtures and module stubs for agent-gateway tests.

livekit-rtc does not publish wheels for Python 3.14 yet.  We stub out the
livekit.rtc and livekit.api modules so tests can import agent_gateway code
without the native extension being present.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _install_livekit_stubs() -> None:
    """Insert lightweight stubs for livekit.rtc and livekit.api into sys.modules."""
    # Only stub if the real submodules are unavailable.
    try:
        from livekit import api, rtc  # noqa: F401

        return  # real modules present — no stub needed
    except ImportError:
        pass

    # Ensure livekit top-level package is present.
    if "livekit" not in sys.modules:
        livekit = types.ModuleType("livekit")
        sys.modules["livekit"] = livekit
    else:
        livekit = sys.modules["livekit"]

    # --- livekit.rtc stub ---
    rtc_stub = types.ModuleType("livekit.rtc")
    rtc_stub.Room = MagicMock(name="rtc.Room")
    rtc_stub.AudioSource = MagicMock(name="rtc.AudioSource")
    rtc_stub.LocalAudioTrack = MagicMock(name="rtc.LocalAudioTrack")
    rtc_stub.TrackPublishOptions = MagicMock(name="rtc.TrackPublishOptions")
    rtc_stub.TrackSource = MagicMock(name="rtc.TrackSource")
    rtc_stub.AudioFrame = MagicMock(name="rtc.AudioFrame")
    rtc_stub.AudioStream = MagicMock(name="rtc.AudioStream")
    rtc_stub.Track = MagicMock(name="rtc.Track")
    rtc_stub.RemoteTrackPublication = MagicMock(name="rtc.RemoteTrackPublication")
    rtc_stub.RemoteParticipant = MagicMock(name="rtc.RemoteParticipant")
    rtc_stub.TrackKind = MagicMock(name="rtc.TrackKind")
    sys.modules["livekit.rtc"] = rtc_stub
    livekit.rtc = rtc_stub

    # --- livekit.api stub ---
    api_stub = types.ModuleType("livekit.api")
    api_stub.AccessToken = MagicMock(name="api.AccessToken")
    api_stub.VideoGrants = MagicMock(name="api.VideoGrants")
    sys.modules["livekit.api"] = api_stub
    livekit.api = api_stub


_install_livekit_stubs()
