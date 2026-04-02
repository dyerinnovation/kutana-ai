# Kutana AI — Local Providers + Provider Docs — Completed

**Date:** 2026-02-27
**Scope:** Local/free providers, mock providers, provider docs, registry updates

## Work Completed

- Added WhisperSTT provider (faster-whisper, local, no API key, CPU int8)
- Added PiperTTS provider (piper-tts, local, no API key, ONNX neural voices)
- Added OllamaLLM provider (httpx REST API, local, no API key, default: mistral)
- Added GroqLLM provider (groq SDK, free cloud tier, no credit card, default: llama-3.1-8b-instant)
- Added MockSTT, MockTTS, MockLLM for deterministic unit testing
- Registered all 4 new providers in the registry (3 STT, 3 TTS, 3 LLM total)
- Updated `__init__.py` re-exports for stt/, tts/, llm/ subpackages
- Created 10 provider setup docs in `docs/providers/` (README + 9 individual guides)
- Updated `.env.example` with OLLAMA_HOST, OLLAMA_MODEL, GROQ_API_KEY, GROQ_MODEL
- Updated `pyproject.toml` optional deps: whisper, piper, groq
- Wrote 48 new tests (96 total, all passing)
- Updated PROGRESS.md, HANDOFF.md, TASKLIST.md

## Work Remaining

- Generate initial Alembic migration (requires Docker)
- Integration tests for providers (requires running Ollama, Groq API key)
- Provider registry integration tests

## Lessons Learned

- **Multiple `tests/__init__.py` causes namespace collision**: When a monorepo has multiple packages each with `tests/__init__.py`, Python's import system sees conflicting `tests` packages. Fix: remove `__init__.py` from test directories — pytest discovers tests without them.
- **venv corruption on `--reinstall`**: Running `uv sync --reinstall` can leave `.pth` files in a broken state. Fix: `rm -rf .venv && uv sync --all-packages` for a clean rebuild.
- **Optional deps need `--all-extras`**: Providers like Groq require `uv sync --all-extras` or `uv sync --extra groq` to install the SDK. Tests should either skip when the optional dep is missing or install all extras in CI.
- **Groq is excellent for local dev**: Free tier (console.groq.com), no credit card, blazing fast LPU inference, OpenAI-compatible API. Highly recommended as the default dev LLM provider.
- **Ruff SIM115 (NamedTemporaryFile)**: Using `NamedTemporaryFile(delete=False)` triggers SIM115. Use `# noqa: SIM115` when you need the file to persist for external readers (e.g., faster-whisper needs the temp WAV path).
