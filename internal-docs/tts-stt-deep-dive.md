# STT/TTS Deep Dive: Phantom Word Detection

**Date:** 2026-03-25
**Issue:** User reports "thank you" appearing in the transcript before they say anything when they unmute/take their speaking turn. The only word they actually say is "testing," which is eventually captured correctly.

---

## 1. How Our STT Pipeline Works

### Data flow (browser → transcript)

```
Browser mic (getUserMedia)
  ↓ Float32 → Int16 PCM16 @ 16 kHz
ScriptProcessorNode (4096 samples = ~256ms chunks)
  ↓ base64-encoded JSON
WebSocket → /human/connect
  ↓
HumanSessionHandler._handle_audio()
  ↓ base64 decode
AudioBridge.process_audio(meeting_id, audio_bytes)
  ↓
AudioPipeline.process_audio(chunk)  [retry + 5 MB buffer]
  ↓
STTProvider.send_audio(chunk)
```

**Two STT providers are in use:**

| Provider | Mode | How it works |
|---|---|---|
| `WhisperRemoteSTT` | Batch (default in prod) | Buffers all PCM16 in memory; POST to vLLM Whisper every 5s |
| `DeepgramSTT` | Streaming | Streams raw PCM16 over WebSocket to Deepgram; returns per-utterance finals |

Transcript segments flow out via Redis Streams → EventRelay → browser `transcript` messages.

### Key files

| File | Role |
|---|---|
| `packages/convene-providers/src/convene_providers/stt/whisper_remote_stt.py` | WhisperRemoteSTT |
| `packages/convene-providers/src/convene_providers/stt/deepgram_stt.py` | DeepgramSTT |
| `services/audio-service/src/audio_service/audio_pipeline.py` | Buffering + retry |
| `services/agent-gateway/src/agent_gateway/human_session.py` | Browser audio intake |
| `web/src/pages/MeetingRoomPage.tsx` | Frontend audio capture |

---

## 2. How STT Works in Meeting Contexts (General Background)

### Real-time streaming STT
Streaming STT (Deepgram, AssemblyAI) works by accepting a continuous raw PCM byte stream and returning:
- **Interim results** — rolling hypothesis, updated as more audio arrives; not yet final
- **Final results** — committed once an endpoint (silence/pause) is detected

The key parameter controlling this is **endpointing**: how much silence (in ms) triggers the end of an utterance and commits a final result. A too-short endpointing value means Deepgram finalizes results based on very small pauses, potentially committing before the speaker has finished. A too-long value adds latency.

### Batch/file STT
Whisper was designed for audio file transcription, not streaming. When used in a meeting context, the common pattern is a **sliding window**: buffer N seconds of audio, transcribe it, clear the buffer, repeat. The challenge is that this creates:
1. **Silence windows**: windows containing mostly silence
2. **Hallucination risk**: Whisper is trained to always produce output; it "fills in" phrases even for silence

### VAD in meeting contexts
Leading platforms (Zoom, Teams, Google Meet) use multiple layers of VAD:
1. **Client-side VAD** (WebRTC VAD or ML-based): suppress transmission of silent frames entirely
2. **Server-side acoustic VAD**: gate transcription to only begin when energy level indicates speech
3. **STT model's own confidence**: Deepgram returns `confidence`; Whisper verbose JSON returns `no_speech_prob`

---

## 3. Speaker Diarization

Diarization = who said what, when.

| Provider | Diarization Method |
|---|---|
| Deepgram (Nova-2) | Enabled via `diarize=true` param; returns `speaker_0`, `speaker_1`, etc. per word |
| Whisper-remote | No diarization — single `speaker_id=None` per segment |

Our current diarization approach assigns speaker labels based on what Deepgram assigns, not tied to which session/participant sent the audio. This means:
- Speaker 0 could be any participant
- Re-joining resets speaker numbering
- No cross-session speaker continuity

This is acceptable for Phase 1 but will need improvement when multi-participant meetings are common.

---

## 4. Common Causes of Phantom Word Detection

### A. Whisper hallucination on silence (PRIMARY cause in our system)

**This is the most likely cause of the "thank you" phantom word.**

Whisper-large-v3 is trained to transcribe audio files. When given an audio file that contains silence, background noise, or ambient sound, it doesn't output an empty string — it outputs a hallucinated phrase. The most common Whisper hallucinations on silence are:

- " Thank you."
- " Thank you for watching."
- " Thanks for watching."
- " you"
- " Okay."
- Various foreign language filler phrases

This is a documented, well-known behavior of Whisper models and has been extensively reported in open-source Whisper implementations (OpenAI/whisper GitHub issues #29, #560, etc.).

**Why it happens in our case:**
1. User unmutes at T=0
2. Audio starts flowing immediately (ScriptProcessorNode always runs)
3. First 5 seconds of audio = ambient room noise (HVAC, fan, microphone hiss)
4. At T=5s, `_consume_segments` calls `whisper.get_transcript()`
5. Whisper processes ~5s of ambient noise and returns " Thank you."
6. That transcript is published to Redis and displayed in the browser
7. User says "testing" at T=7s, captured correctly in the next 5s window

**Why `no_speech_prob` is the right filter:**
Whisper's `verbose_json` response includes `no_speech_prob` per segment — Whisper's own estimate of the probability that the segment contains no real speech. On silence/ambient-noise segments, this is typically 0.6–0.99. We were not using it at all.

### B. Audio stream startup artifacts

When `ScriptProcessorNode` first connects and the OS audio subsystem initializes, there can be a brief burst of non-representative audio:
- Initial click/pop from mic activation
- AGC (Automatic Gain Control) ramping up
- Browser audio graph initialization noise

These transients are very short but can confuse STT models.

### C. Missing endpointing configuration (Deepgram)

Our Deepgram params omit `endpointing`, so Deepgram uses its server-side default (very aggressive silence detection, ~10ms). This means:
- Small natural pauses within a sentence may be treated as utterance boundaries
- Background noise during a pause may trigger a final result
- Ambient noise before the user speaks can be committed as a final utterance

### D. No client-side energy gate

The frontend sends audio frames at ~256ms intervals regardless of whether there is actual speech energy. Every frame — including pure silence — is base64-encoded and sent over WebSocket. This:
- Sends more ambient noise to STT providers than necessary
- For Whisper: increases the amount of silence in each 5s buffer
- For Deepgram: streams silence that may trigger low-confidence false finals

### E. TTS echo (not currently an issue, but worth monitoring)

If TTS audio from an AI agent were to loop back through the microphone (acoustic echo), that AI speech would be re-transcribed. Our current architecture sends TTS via a separate `tts.audio` WebSocket event (not through the audio pipeline), so this is not happening. However, if a user is not using headphones, TTS speaker output can be picked up by their microphone.

---

## 5. What Leading Platforms Do

### Deepgram's recommended approach for live meetings
- Enable `vad_events=true` to receive `SpeechStarted` / `UtteranceEnd` events
- Set `endpointing=300` or higher for meeting contexts (vs. real-time interaction where 100ms is used)
- Set `utterance_end_ms=2000` for a longer silence window before committing
- Apply `smart_format=true` to clean up output

### Whisper for live meeting audio
- Do **not** feed Whisper silence. Use an acoustic VAD (e.g., Silero VAD, py-webrtcvad) to gate what you send.
- Check `no_speech_prob` on every segment — Whisper itself tells you when it's hallucinating. Threshold of 0.5 eliminates most hallucinations.
- The `compression_ratio_threshold` parameter (default 2.4) can help: very high compression ratios indicate hallucinated repetitive text.
- `temperature=0` (default) reduces hallucination vs higher temperatures.

### Client-side energy VAD
WebRTC's built-in `noiseSuppression` and `echoCancellation` (which we already use) help significantly. Adding an explicit RMS energy gate before transmitting audio chunks is standard practice in meeting apps:
- Google Meet uses a ~-40 dBFS threshold before sending audio to the backend
- Zoom applies VAD at the audio capture layer before WebRTC encoding
- Common threshold: RMS of 0.01 (Float32 normalized) ≈ -40 dBFS

---

## 6. Root Cause Summary

| Cause | Provider affected | Severity | Fixed? |
|---|---|---|---|
| Whisper hallucination on silence — `no_speech_prob` not filtered | Whisper-remote | **Critical** | ✅ Fixed |
| No `endpointing` param — too-aggressive silence detection | Deepgram | High | ✅ Fixed |
| No confidence threshold — low-confidence results accepted | Both | Medium | ✅ Fixed |
| No client-side energy VAD — silence sent to backend | Both | Medium | ✅ Fixed |
| TTS echo (acoustic feedback through mic) | Both | Low (not active) | N/A |

---

## 7. Fixes Implemented

### Fix 1: Whisper `no_speech_prob` filtering (`whisper_remote_stt.py`)

Added a `no_speech_threshold` parameter (default `0.5`). Any segment where Whisper's own `no_speech_prob ≥ 0.5` is dropped before yielding. This is Whisper's self-reported confidence that a segment contains no real speech — it is the most reliable single filter for hallucinations.

Also added a `min_confidence` parameter (default `0.0`, i.e. no floor by default for Whisper since logprob-derived confidence is less reliable) so callers can tune further.

### Fix 2: Deepgram endpointing + confidence floor (`deepgram_stt.py`)

Added `endpointing=400` (400ms of silence triggers a final utterance), `smart_format=true`, and a `min_confidence=0.65` threshold. Deepgram's confidence scores are well-calibrated — scores below 0.65 are almost always noise or background audio.

### Fix 3: Client-side energy VAD (`MeetingRoomPage.tsx`)

Added an RMS energy check before sending each 4096-sample frame to the backend. Frames with RMS < 0.01 (~-40 dBFS) are silently dropped. This is the same threshold used by major meeting platforms. The effect:
- Dramatically reduces the amount of silence that reaches Whisper's buffer
- Prevents Deepgram from seeing sustained silence as a speaking event
- Reduces WebSocket bandwidth by 60–90% in typical meetings

---

## 8. Testing the Fix

To verify the phantom words are resolved:
1. Join a meeting, say nothing for 15–20 seconds (several Whisper windows)
2. No transcript should appear
3. Say "testing" clearly once
4. Transcript should show "testing" (or similar) with no phantom words before it

To confirm the energy VAD is working:
- Open browser devtools → Network → WS tab
- While silent, the WebSocket should send very few messages (only those above the energy threshold)
- While speaking, messages should flow freely
