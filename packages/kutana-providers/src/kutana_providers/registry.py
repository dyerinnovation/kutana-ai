"""Provider registry with factory pattern for STT, TTS, and LLM providers."""

from __future__ import annotations

import enum
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProviderType(enum.StrEnum):
    """Categories of providers managed by the registry."""

    STT = "stt"
    TTS = "tts"
    LLM = "llm"
    MESSAGE_BUS = "message_bus"
    EXTRACTOR = "extractor"
    TURN_MANAGER = "turn_manager"
    CHAT_STORE = "chat_store"


class ProviderRegistry:
    """Registry for provider classes with factory-based instantiation.

    Maintains a mapping of (ProviderType, name) to provider classes.
    Supports registration, creation, and listing of providers.

    Example:
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "assemblyai", AssemblyAISTT)
        provider = registry.create(
            ProviderType.STT, "assemblyai", api_key="..."
        )
    """

    def __init__(self) -> None:
        """Initialize an empty provider registry."""
        self._providers: dict[tuple[ProviderType, str], type[Any]] = {}

    def register(
        self,
        provider_type: ProviderType,
        name: str,
        cls: type[Any],
    ) -> None:
        """Register a provider class under a type and name.

        Args:
            provider_type: The category of provider (STT, TTS, LLM).
            name: A unique name for this provider within its type.
            cls: The provider class to register.

        Raises:
            ValueError: If a provider with the same type and name is
                already registered.
        """
        key = (provider_type, name)
        if key in self._providers:
            msg = f"Provider already registered: {provider_type.value}/{name}"
            raise ValueError(msg)
        self._providers[key] = cls
        logger.debug(
            "Registered provider: %s/%s -> %s",
            provider_type.value,
            name,
            cls.__name__,
        )

    def create(
        self,
        provider_type: ProviderType,
        name: str,
        **kwargs: Any,
    ) -> Any:
        """Instantiate a registered provider with the given arguments.

        Args:
            provider_type: The category of provider to create.
            name: The registered name of the provider.
            **kwargs: Arguments to pass to the provider constructor.

        Returns:
            An instance of the registered provider class.

        Raises:
            KeyError: If no provider is registered with the given
                type and name.
        """
        key = (provider_type, name)
        cls = self._providers.get(key)
        if cls is None:
            available = self.list_providers(provider_type)
            msg = f"No provider registered for {provider_type.value}/{name}. Available: {available}"
            raise KeyError(msg)
        return cls(**kwargs)

    def list_providers(self, provider_type: ProviderType) -> list[str]:
        """List all registered provider names for a given type.

        Args:
            provider_type: The category of providers to list.

        Returns:
            Sorted list of registered provider names.
        """
        names = [name for (ptype, name) in self._providers if ptype == provider_type]
        return sorted(names)

    def is_registered(self, provider_type: ProviderType, name: str) -> bool:
        """Check whether a provider is registered.

        Args:
            provider_type: The category of provider.
            name: The provider name to check.

        Returns:
            True if the provider is registered, False otherwise.
        """
        return (provider_type, name) in self._providers


def _build_default_registry() -> ProviderRegistry:
    """Build a registry with all built-in providers pre-registered.

    Returns:
        A ProviderRegistry instance with default providers registered.
    """
    from kutana_providers.chat.redis_chat_store import RedisChatStore
    from kutana_providers.extraction.llm_extractor import LLMExtractor
    from kutana_providers.llm.anthropic_llm import AnthropicLLM
    from kutana_providers.llm.groq_llm import GroqLLM
    from kutana_providers.llm.ollama_llm import OllamaLLM
    from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus
    from kutana_providers.messaging.gcp_pubsub import PubSubMessageBus
    from kutana_providers.messaging.nats_jetstream import NATSMessageBus
    from kutana_providers.messaging.redis_streams import RedisStreamsMessageBus
    from kutana_providers.stt.assemblyai_stt import AssemblyAISTT
    from kutana_providers.stt.deepgram_stt import DeepgramSTT
    from kutana_providers.stt.whisper_remote_stt import WhisperRemoteSTT
    from kutana_providers.stt.whisper_stt import WhisperSTT
    from kutana_providers.tts.cartesia_tts import CartesiaTTS
    from kutana_providers.tts.elevenlabs_tts import ElevenLabsTTS
    from kutana_providers.tts.piper_tts import PiperTTS
    from kutana_providers.turn_management.redis_turn_manager import RedisTurnManager

    registry = ProviderRegistry()

    # STT providers
    registry.register(ProviderType.STT, "assemblyai", AssemblyAISTT)
    registry.register(ProviderType.STT, "deepgram", DeepgramSTT)
    registry.register(ProviderType.STT, "whisper", WhisperSTT)
    registry.register(ProviderType.STT, "whisper-remote", WhisperRemoteSTT)

    # TTS providers
    registry.register(ProviderType.TTS, "cartesia", CartesiaTTS)
    registry.register(ProviderType.TTS, "elevenlabs", ElevenLabsTTS)
    registry.register(ProviderType.TTS, "piper", PiperTTS)

    # LLM providers
    registry.register(ProviderType.LLM, "anthropic", AnthropicLLM)
    registry.register(ProviderType.LLM, "ollama", OllamaLLM)
    registry.register(ProviderType.LLM, "groq", GroqLLM)

    # Message bus providers
    registry.register(ProviderType.MESSAGE_BUS, "redis", RedisStreamsMessageBus)
    registry.register(ProviderType.MESSAGE_BUS, "aws-sns-sqs", SQSMessageBus)
    registry.register(ProviderType.MESSAGE_BUS, "gcp-pubsub", PubSubMessageBus)
    registry.register(ProviderType.MESSAGE_BUS, "nats", NATSMessageBus)

    # Extractor providers
    registry.register(ProviderType.EXTRACTOR, "llm", LLMExtractor)

    # Turn manager providers
    registry.register(ProviderType.TURN_MANAGER, "redis", RedisTurnManager)

    # Chat store providers
    registry.register(ProviderType.CHAT_STORE, "redis", RedisChatStore)

    return registry


#: Default singleton registry with all built-in providers.
default_registry: ProviderRegistry = _build_default_registry()
