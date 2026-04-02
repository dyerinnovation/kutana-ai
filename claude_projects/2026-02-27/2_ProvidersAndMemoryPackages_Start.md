# Plan: Create `packages/kutana-providers/` and `packages/kutana-memory/`

## Objective
Create the full `kutana-providers` and `kutana-memory` packages for the Kutana AI monorepo.
Since `kutana-core` only has `__init__.py` and `pyproject.toml`, we must also create the
kutana-core models, interfaces, and events that these packages depend on.

## Prerequisites
- kutana-core interfaces: STTProvider, TTSProvider, LLMProvider ABCs
- kutana-core models: TranscriptSegment, Task, Decision, Meeting, Voice, MemoryContext

## Package 1: kutana-providers
STT, TTS, and LLM provider implementations behind the core ABCs.

### Files
1. `packages/kutana-providers/pyproject.toml`
2. `packages/kutana-providers/src/kutana_providers/__init__.py`
3. `packages/kutana-providers/src/kutana_providers/stt/__init__.py`
4. `packages/kutana-providers/src/kutana_providers/stt/assemblyai_stt.py`
5. `packages/kutana-providers/src/kutana_providers/stt/deepgram_stt.py`
6. `packages/kutana-providers/src/kutana_providers/tts/__init__.py`
7. `packages/kutana-providers/src/kutana_providers/tts/cartesia_tts.py`
8. `packages/kutana-providers/src/kutana_providers/tts/elevenlabs_tts.py`
9. `packages/kutana-providers/src/kutana_providers/llm/__init__.py`
10. `packages/kutana-providers/src/kutana_providers/llm/anthropic_llm.py`
11. `packages/kutana-providers/src/kutana_providers/registry.py`
12. `packages/kutana-providers/tests/__init__.py`

### Providers
- **STT**: AssemblyAI (WebSocket streaming), Deepgram (WebSocket streaming)
- **TTS**: Cartesia (HTTP streaming), ElevenLabs (HTTP streaming)
- **LLM**: Anthropic Claude (task extraction, summarization, reporting)

## Package 2: kutana-memory
Four-layer memory system: working, short-term, long-term, structured.

### Files
1. `packages/kutana-memory/pyproject.toml`
2. `packages/kutana-memory/src/kutana_memory/__init__.py`
3. `packages/kutana-memory/src/kutana_memory/working.py`
4. `packages/kutana-memory/src/kutana_memory/short_term.py`
5. `packages/kutana-memory/src/kutana_memory/long_term.py`
6. `packages/kutana-memory/src/kutana_memory/structured.py`
7. `packages/kutana-memory/tests/__init__.py`

## Dependencies to create first (in kutana-core)
- `packages/kutana-core/src/kutana_core/models/__init__.py`
- `packages/kutana-core/src/kutana_core/models/meeting.py`
- `packages/kutana-core/src/kutana_core/models/participant.py`
- `packages/kutana-core/src/kutana_core/models/task.py`
- `packages/kutana-core/src/kutana_core/models/decision.py`
- `packages/kutana-core/src/kutana_core/models/transcript.py`
- `packages/kutana-core/src/kutana_core/models/agent.py`
- `packages/kutana-core/src/kutana_core/interfaces/__init__.py`
- `packages/kutana-core/src/kutana_core/interfaces/stt.py`
- `packages/kutana-core/src/kutana_core/interfaces/tts.py`
- `packages/kutana-core/src/kutana_core/interfaces/llm.py`
- `packages/kutana-core/src/kutana_core/events/__init__.py`
- `packages/kutana-core/src/kutana_core/events/definitions.py`

## Approach
1. Create kutana-core dependency files (models, interfaces, events)
2. Create kutana-providers package
3. Create kutana-memory package
4. Verify all imports are correct
