"""Audio adapters for kutana-providers.

Provides LiveKit audio integration (requires the ``livekit`` optional dep).
Import-guarded so missing the optional dep does not break the package.
"""

from __future__ import annotations

__all__: list[str] = []

try:
    from kutana_providers.audio.livekit_adapter import LiveKitAudioAdapter as LiveKitAudioAdapter

    __all__.append("LiveKitAudioAdapter")
except ImportError:
    pass

try:
    from kutana_providers.audio.livekit_publisher import (
        LiveKitAudioPublisher as LiveKitAudioPublisher,  # type: ignore[import]
    )

    __all__.append("LiveKitAudioPublisher")
except ImportError:
    pass
