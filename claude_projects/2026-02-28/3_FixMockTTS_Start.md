# Plan: Fix MockTTS Missing `close()` Abstract Method

## Date: 2026-02-28

## Overview
`TestMockTTS.test_is_tts_provider` fails because `MockTTS` is missing the `close()` abstract method required by `TTSProvider` ABC. Add a no-op implementation.

## File to Modify
- `packages/kutana-providers/src/kutana_providers/testing.py` — add `async def close(self) -> None` to `MockTTS`
