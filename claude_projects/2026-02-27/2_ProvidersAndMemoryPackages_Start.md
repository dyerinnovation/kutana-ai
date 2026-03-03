# Plan: Create `packages/convene-providers/` and `packages/convene-memory/`

## Objective
Create the full `convene-providers` and `convene-memory` packages for the Convene AI monorepo.
Since `convene-core` only has `__init__.py` and `pyproject.toml`, we must also create the
convene-core models, interfaces, and events that these packages depend on.

## Prerequisites
- convene-core interfaces: STTProvider, TTSProvider, LLMProvider ABCs
- convene-core models: TranscriptSegment, Task, Decision, Meeting, Voice, MemoryContext

## Package 1: convene-providers
STT, TTS, and LLM provider implementations behind the core ABCs.

### Files
1. `packages/convene-providers/pyproject.toml`
2. `packages/convene-providers/src/convene_providers/__init__.py`
3. `packages/convene-providers/src/convene_providers/stt/__init__.py`
4. `packages/convene-providers/src/convene_providers/stt/assemblyai_stt.py`
5. `packages/convene-providers/src/convene_providers/stt/deepgram_stt.py`
6. `packages/convene-providers/src/convene_providers/tts/__init__.py`
7. `packages/convene-providers/src/convene_providers/tts/cartesia_tts.py`
8. `packages/convene-providers/src/convene_providers/tts/elevenlabs_tts.py`
9. `packages/convene-providers/src/convene_providers/llm/__init__.py`
10. `packages/convene-providers/src/convene_providers/llm/anthropic_llm.py`
11. `packages/convene-providers/src/convene_providers/registry.py`
12. `packages/convene-providers/tests/__init__.py`

### Providers
- **STT**: AssemblyAI (WebSocket streaming), Deepgram (WebSocket streaming)
- **TTS**: Cartesia (HTTP streaming), ElevenLabs (HTTP streaming)
- **LLM**: Anthropic Claude (task extraction, summarization, reporting)

## Package 2: convene-memory
Four-layer memory system: working, short-term, long-term, structured.

### Files
1. `packages/convene-memory/pyproject.toml`
2. `packages/convene-memory/src/convene_memory/__init__.py`
3. `packages/convene-memory/src/convene_memory/working.py`
4. `packages/convene-memory/src/convene_memory/short_term.py`
5. `packages/convene-memory/src/convene_memory/long_term.py`
6. `packages/convene-memory/src/convene_memory/structured.py`
7. `packages/convene-memory/tests/__init__.py`

## Dependencies to create first (in convene-core)
- `packages/convene-core/src/convene_core/models/__init__.py`
- `packages/convene-core/src/convene_core/models/meeting.py`
- `packages/convene-core/src/convene_core/models/participant.py`
- `packages/convene-core/src/convene_core/models/task.py`
- `packages/convene-core/src/convene_core/models/decision.py`
- `packages/convene-core/src/convene_core/models/transcript.py`
- `packages/convene-core/src/convene_core/models/agent.py`
- `packages/convene-core/src/convene_core/interfaces/__init__.py`
- `packages/convene-core/src/convene_core/interfaces/stt.py`
- `packages/convene-core/src/convene_core/interfaces/tts.py`
- `packages/convene-core/src/convene_core/interfaces/llm.py`
- `packages/convene-core/src/convene_core/events/__init__.py`
- `packages/convene-core/src/convene_core/events/definitions.py`

## Approach
1. Create convene-core dependency files (models, interfaces, events)
2. Create convene-providers package
3. Create convene-memory package
4. Verify all imports are correct
