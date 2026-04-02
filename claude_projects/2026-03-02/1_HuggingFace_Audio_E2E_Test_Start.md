# Download HuggingFace Test Audio & Run E2E Test

## Objective
Download a real speech audio file from HuggingFace, update the E2E test script with `--output-file` support, and run the full E2E test against the gateway + DGX Spark Whisper.

## Steps

1. **Create data directory structure** — `data/input/` and `data/output/`, add `data/` to `.gitignore`
2. **Download speech audio** — LibriSpeech sample from HuggingFace
3. **Convert FLAC to WAV** — 16kHz mono PCM16 via ffmpeg
4. **Start Redis** — `docker compose up redis -d`
5. **Start Agent Gateway** — with `whisper-remote` STT provider pointing to DGX Spark
6. **Update test script** — Add `--output-file` flag to `scripts/test_e2e_gateway.py`
7. **Run E2E test** — With real audio file
8. **Report results** — Read output JSON and summarize

## Files Modified
- `data/input/` — new directory for test audio
- `data/output/` — new directory for test results
- `.gitignore` — add `data/`
- `scripts/test_e2e_gateway.py` — add `--output-file` flag with structured JSON output

## Key Details
- Audio: LibriSpeech sample from `facebook/wav2vec2-large-960h` repo
- Gateway URL: `ws://localhost:8003`
- STT: `whisper-remote` pointing to `http://spark-b0f2.local/kutana-stt/v1`
- Output format: JSON with timestamp, meeting ID, audio info, all messages, summary
