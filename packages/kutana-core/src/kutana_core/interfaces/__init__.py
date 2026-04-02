"""Kutana AI provider interfaces (ABCs)."""

from __future__ import annotations

from kutana_core.interfaces.chat_store import ChatStore
from kutana_core.interfaces.llm import LLMProvider
from kutana_core.interfaces.stt import STTProvider
from kutana_core.interfaces.tts import TTSProvider, Voice
from kutana_core.interfaces.turn_manager import TurnManager

__all__ = [
    "ChatStore",
    "LLMProvider",
    "STTProvider",
    "TTSProvider",
    "TurnManager",
    "Voice",
]
