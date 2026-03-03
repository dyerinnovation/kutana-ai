# E2E Gateway Test Readiness — Plan

**Date**: 2026-03-01
**Objective**: Fix critical bugs preventing the E2E flow and create test tooling so you can manually verify: agent connects via WebSocket, sends audio, receives transcript segments back.

## Bugs to Fix

1. **`_consume_segments` exits immediately** — single-pass design; needs periodic loop
2. **Whisper providers don't clear buffer** — repeated calls re-transcribe old audio
3. **WhisperSTT confidence bug** — `avg_logprob` is negative, fails 0.0-1.0 validation

## Deliverables

1. Fix AudioBridge `_consume_segments` (periodic loop)
2. Fix both Whisper providers (buffer clear + confidence)
3. Create `scripts/test_e2e_gateway.py` (WebSocket test client)
4. Create `docs/manual-testing/E2E_Gateway_Test.md` (walkthrough doc)
5. Update tests for the loop change

## STT Provider

Whisper Remote on DGX Spark (`http://spark-b0f2.local/convene-stt/v1`)
