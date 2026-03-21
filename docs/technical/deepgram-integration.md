# Deepgram STT Integration

## Overview
Convene AI uses Deepgram as its primary Speech-to-Text (STT) provider. Deepgram is a cloud API service — audio goes in, transcribed text with speaker labels comes back. No self-hosted infrastructure needed.

## Why Deepgram
- **Accuracy:** Nova-3 achieves 5.26% WER (word error rate), leading independent benchmarks
- **Latency:** Sub-300ms for real-time streaming
- **Cost:** $0.0077/min streaming, $0.0043/min batch (Pay-As-You-Go)
- **Diarization:** Speaker identification with word-level labels, no speaker cap
- **Simplicity:** API key + SDK, no GPU or model deployment

## Configuration
```
CONVENE_STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=<your-key>
DEEPGRAM_MODEL=nova-3
```

## API Parameters Used
| Parameter | Value | Purpose |
|-----------|-------|---------|
| model | nova-3 | Latest, most accurate model |
| diarize | true | Speaker identification |
| smart_format | true | Auto-punctuation, capitalization |
| utterances | true | Logical speech segmentation |
| interim_results | true | Partial results for real-time display |
| encoding | linear16 | 16-bit PCM audio format |
| sample_rate | 16000 | 16kHz audio |

## Data Flow
1. Audio from meeting (LiveKit/WebRTC) → audio service
2. Audio service opens WebSocket to `wss://api.deepgram.com/v1/listen`
3. Raw audio chunks streamed to Deepgram
4. Deepgram returns: transcribed text, word-level timestamps, speaker IDs, confidence scores
5. Audio service publishes segments to MessageBus: `meeting.{id}.transcript`
6. Extraction pipeline processes transcript segments in batches

## Diarization Response Format
Each word includes a `speaker` integer and `speaker_confidence` float. Speaker IDs are consistent within a session but not across sessions. The extraction pipeline uses speaker labels to attribute tasks, decisions, and other entities to specific participants.

## Per-Tier Configuration
| Tier | Model | Diarization | Features |
|------|-------|-------------|----------|
| Free | Nova-3 (capped) | No | Basic transcription |
| Pro | Nova-3 | Yes | Full features |
| Business | Nova-3 | Yes | + batch re-processing, custom vocabulary |
| Enterprise | Nova-3 or self-hosted Whisper | Yes | + on-prem option |

## Provider Abstraction
Deepgram is registered in the provider registry as the "deepgram" STT provider. The STT ABC allows swapping to Google Cloud STT, AWS Transcribe, or self-hosted faster-whisper without code changes. Enterprise customers requiring data sovereignty use self-hosted Whisper + pyannote.audio for diarization.

## SDK
Official Python SDK: `deepgram-sdk` on PyPI. Supports async WebSocket streaming via `AsyncDeepgramClient`.

## Free Credits
New Deepgram accounts receive $200 in free credit (~26,000 minutes of streaming). Sufficient for full development and testing.
