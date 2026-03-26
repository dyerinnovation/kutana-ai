# Fix Meeting Transcription — STT Pipeline

## Problem
Meeting transcription broken — agent-gateway crashes with `ValueError: STT_API_KEY is required for deepgram provider` when human sends audio. Deepgram API key exists but was never set in helm values.

## Plan
1. Set `secrets.deepgramApiKey` in `charts/convene/values.yaml` (base64-encoded)
2. Remove `bypassPermissions` from Claude Code `settings.json`
3. Commit, push, deploy via helm upgrade
4. Verify transcription works in browser
