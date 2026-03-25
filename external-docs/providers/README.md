# Provider Setup Guide

Overview of all available STT, TTS, and LLM providers.

## Provider Matrix

| Provider | Type | Local? | API Key? | Best For |
|----------|------|--------|----------|----------|
| **Whisper** | STT | Yes | No | Local dev, testing |
| **AssemblyAI** | STT | No | Yes | Production (real-time, diarization) |
| **Deepgram** | STT | No | Yes | Production (real-time, low latency) |
| **Piper** | TTS | Yes | No | Local dev, testing |
| **Cartesia** | TTS | No | Yes | Production (low latency, natural) |
| **ElevenLabs** | TTS | No | Yes | Production (voice cloning, quality) |
| **Ollama** | LLM | Yes | No | Local dev, offline |
| **Groq** | LLM | No | Free | Dev (fast, free tier, no CC) |
| **Anthropic** | LLM | No | Yes | Production (best extraction quality) |

## Quick Start (Local Development)

For local development with no API keys needed:
1. Install local providers: `uv sync --all-packages`
2. Install Ollama: `brew install ollama && ollama pull mistral`
3. Start Ollama: `ollama serve`
4. Use providers: whisper (STT), piper (TTS), ollama (LLM)

## Provider Selection by Use Case

- **Local dev/testing**: whisper + piper + ollama (no API keys, works offline)
- **Free cloud dev**: whisper + piper + groq (best quality without paying)
- **Production**: assemblyai/deepgram + cartesia/elevenlabs + anthropic

## Registry Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create a cloud STT provider
stt = default_registry.create(ProviderType.STT, "assemblyai", api_key="your-key")

# Create an Anthropic LLM provider
llm = default_registry.create(ProviderType.LLM, "anthropic", api_key="sk-ant-...")

# List available providers for a type
stt_providers = default_registry.list_providers(ProviderType.STT)
# Returns: ["assemblyai", "deepgram"]
```

## Individual Provider Docs

- **STT**: [Whisper](whisper-stt.md) | [AssemblyAI](assemblyai-stt.md) | [Deepgram](deepgram-stt.md)
- **TTS**: [Piper](piper-tts.md) | [Cartesia](cartesia-tts.md) | [ElevenLabs](elevenlabs-tts.md)
- **LLM**: [Ollama](ollama-llm.md) | [Groq](groq-llm.md) | [Anthropic](anthropic-llm.md)
