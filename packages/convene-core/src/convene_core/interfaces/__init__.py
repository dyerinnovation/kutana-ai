"""Convene AI provider interfaces (ABCs)."""

from __future__ import annotations

from convene_core.interfaces.chat_store import ChatStore
from convene_core.interfaces.llm import LLMProvider
from convene_core.interfaces.stt import STTProvider
from convene_core.interfaces.tts import TTSProvider, Voice
from convene_core.interfaces.turn_manager import TurnManager

__all__ = [
    "ChatStore",
    "LLMProvider",
    "STTProvider",
    "TTSProvider",
    "TurnManager",
    "Voice",
]
