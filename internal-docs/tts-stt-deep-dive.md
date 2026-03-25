# STT/TTS Deep Dive: Phantom Word Detection

**Date:** 2026-03-25 (updated 2026-03-25 round 2)
**Issue:** User sees "I'm sorry - I'm sorry - I'm sorry" (and previously "Thank you") repeated dozens of times in the transcript when they haven't spoken anything.

---

## 1. How Our STT Pipeline Works

### Data flow (browser → transcript)

```
Browser mic (getUserMedia)
  ↓ Float32 → Int16 PCM16 @ 16 kHz
ScriptProcessorNode (4096 samples = ~256ms chunks)
  ↓ Energy gate: RMS < 0.01 → drop frame
  ↓ base64-encoded JSON
WebSocket → /human/connect
  ↓
HumanSessionHandler._handle_audio()
  ↓ base64 decode
AudioBridge.process_audio(meeting_id, audio_bytes)
  ↓
AudioPipeline.process_audio(chunk)  [retry + 5 MB buffer]
  ↓
WhisperRemoteSTT.send_audio(chunk)  [buffer accumulates for 5s]
  ↓ every 5s
WhisperRemoteSTT.get_transcript()   [POST WAV to vLLM, apply filters]
  ↓
TranscriptSegmentFinal → Redis Streams → EventRelay → browser
```

**Two STT providers are in use:**

| Provider | Mode | How it works |
|---|---|---|
| `WhisperRemoteSTT` | Batch (default in prod) | Buffers all PCM16 in memory; POST to vLLM Whisper every 5s |
| `DeepgramSTT` | Streaming | Streams raw PCM16 over WebSocket to Deepgram; returns per-utterance finals |

---

## 2. Root Cause: Whisper Fallback Temperature Sampling

### What is fallback temperature sampling?

Whisper uses a beam-search decoding strategy with `temperature=0.0` by default. When the model is **not confident** in its output (the log-probability or compression ratio exceeds internal thresholds), it automatically retries with increasing temperature values: 0.0 → 0.2 → 0.4 → 0.6 → 0.8 → 1.0.

At higher temperatures, the output becomes more "creative" — meaning it hallucinates phrases that are common in training data. The most common hallucinations on ambient noise / HVAC hiss / microphone hiss are:

- "Thank you."
- "I'm sorry."
- "- I'm sorry. - I'm sorry." (doubled, with dashes)
- "Thanks for watching."

This is a well-documented, inherent behavior of Whisper models. See: OpenAI/whisper GitHub issues #29, #560.

### Observed log evidence

From the DGX agent-gateway logs during the user's session (2026-03-25):

```
Whisper POST: buffer_size=155648 audio_duration=4.86s → elapsed=0.15s → yielded 1 segments
Whisper POST: buffer_size=147456 audio_duration=4.61s → elapsed=4.76s → yielded 53 segments
Whisper POST: buffer_size=106496 audio_duration=3.33s → elapsed=4.76s → yielded 36 segments
Whisper POST: buffer_size=40960  audio_duration=1.28s → elapsed=4.82s → yielded 27 segments
Whisper POST: buffer_size=65536  audio_duration=2.05s → elapsed=4.80s → yielded 29 segments
```

Two distinct response patterns:
1. **Fast responses (~0.15s)**: 1 clean segment — real speech, Whisper is confident, decodes immediately
2. **Slow responses (~4.8s)**: 27–53 hallucinated segments — ambient noise, Whisper loops through all fallback temperatures (taking ~4.8s total) and outputs a flood of "- I'm sorry. - I'm sorry." segments

The segment content from the slow responses:
```
Segment: "- I'm sorry. - I'm sorry."   (× 28 consecutive)
Segment: "- I'm sorry. - I'm sorry. - I'm sorry."
Segment: "you"
```

At 36 segments in 3.33 seconds, each segment is ~0.092 seconds long — **impossible for real speech**.

### Why the energy gate alone is insufficient

The RMS energy gate (threshold 0.01 ≈ -40 dBFS) prevents pure silence from being sent. However, ambient room noise (HVAC, fan, microphone hiss) is typically at -35 to -25 dBFS — well above the threshold. The gate correctly lets this through because it *might* be quiet speech. The issue is what Whisper does with it on the backend.

### Why the previous fix (first round) didn't work

The `no_speech_prob` filter was added to `whisper_remote_stt.py` in round 1, but **it was never deployed to the DGX**. The containers continued running old code. Evidence: the log message format on DGX was `"Whisper yielded X segments"` (old format) rather than `"Whisper yielded X segments, dropped Y"` (new format from round 1 commit).

Additionally, even if it had been deployed, `no_speech_prob` alone is unreliable for the fallback-temperature hallucinations: Whisper is so confused by the ambient noise that it sometimes assigns `no_speech_prob < 0.35` even for "I'm sorry" hallucinations (it partially "believes" it heard something).

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

## 4. Complete Hallucination Cause Analysis

### A. Whisper fallback temperature sampling (PRIMARY cause)

**Pattern:** 27–53 segments per 5s window, each ~0.09s, all containing "I'm sorry." or "Thank you."

**Why:** Whisper retries with increasing temperature on low-confidence audio. At high temperatures on ambient noise, it outputs the most statistically common phrases from training data.

**Fix:** Segment duration gate — any segment < 0.15s is impossible real speech.

### B. `no_speech_prob` insufficient as sole filter

**Pattern:** "I'm sorry" hallucinations with `no_speech_prob` below the 0.5 threshold.

**Why:** Whisper partially "believes" it detected something in the noise.

**Fix:** Lower threshold to 0.35 + add independent gates.

### C. Missing compression ratio check

**Pattern:** Repetitive text like "I'm sorry. I'm sorry. I'm sorry." compresses extremely well.

**Why:** Whisper's own `compression_ratio` field in verbose_json flags this, but we weren't checking it.

**Fix:** Drop segments with `compression_ratio > 2.4` (Whisper's own internal default).

### D. Known phrase blocklist missing

**Pattern:** "thank you", "i'm sorry", etc. are known training-data artifacts.

**Fix:** Exact-match blocklist (case-insensitive, punctuation-stripped).

### E. Intra-segment repetition

**Pattern:** Single segment text = "- I'm sorry. - I'm sorry." (phrase repeated within the segment).

**Fix:** Regex repetition detector.

### F. Plain text fallback bypassed all filtering (BUG)

**Pattern:** When vLLM returns `{"text": "I'm sorry.", "segments": []}`, the code was yielding the text unconditionally with confidence=1.0.

**Fix:** Apply hallucination blocklist to the fallback path.

### G. Cross-call deduplication missing

**Pattern:** Same hallucinated phrase appearing in two consecutive 5s windows.

**Fix:** Track `_last_text`; skip if identical to previous emission.

### H. No client-side energy gate (fixed in round 1)

**Pattern:** Every 256ms audio frame sent to backend regardless of content.

**Fix:** RMS energy gate, threshold 0.01 (~-40 dBFS). Already deployed.

### I. No Deepgram endpointing config (fixed in round 1)

**Pattern:** Deepgram defaults to aggressive silence detection.

**Fix:** `endpointing=400ms`, `min_confidence=0.65`. Already deployed.

---

## 5. What Leading Platforms Do

### Deepgram's recommended approach for live meetings
- Enable `vad_events=true` to receive `SpeechStarted` / `UtteranceEnd` events
- Set `endpointing=300` or higher for meeting contexts (vs. real-time interaction where 100ms is used)
- Set `utterance_end_ms=2000` for a longer silence window before committing
- Apply `smart_format=true` to clean up output

### Whisper for live meeting audio
- Do **not** feed Whisper silence. Use an acoustic VAD (e.g., Silero VAD, py-webrtcvad) to gate what you send.
- Check `no_speech_prob` on every segment — threshold 0.35 is a safe balance.
- Check `compression_ratio` — > 2.4 means repetitive/hallucinated text.
- Check segment duration — < 0.15s is not real speech.
- Blocklist known hallucination phrases.
- The `temperature=0` (default) is good; the problem is the automatic fallback to higher temperatures on ambient noise.

### Client-side energy VAD
WebRTC's built-in `noiseSuppression` and `echoCancellation` (which we already use) help significantly. Adding an explicit RMS energy gate before transmitting audio chunks is standard practice:
- Google Meet uses a ~-40 dBFS threshold before sending audio to the backend
- Zoom applies VAD at the audio capture layer before WebRTC encoding
- Common threshold: RMS of 0.01 (Float32 normalized) ≈ -40 dBFS

---

## 6. Root Cause Summary

| Cause | Provider affected | Severity | Fixed? |
|---|---|---|---|
| Whisper fallback temperature → tiny segments flood | Whisper-remote | **Critical** | ✅ Round 2 — duration gate |
| `no_speech_prob` threshold too high (0.5) | Whisper-remote | High | ✅ Round 2 — lowered to 0.35 |
| Missing compression ratio check | Whisper-remote | High | ✅ Round 2 |
| No known-phrase blocklist | Whisper-remote | High | ✅ Round 2 |
| Plain text fallback bypassed all filtering | Whisper-remote | High | ✅ Round 2 |
| Missing intra-segment repetition detection | Whisper-remote | Medium | ✅ Round 2 |
| Missing cross-call deduplication | Whisper-remote | Medium | ✅ Round 2 |
| No client-side energy VAD | Both | Medium | ✅ Round 1 |
| No Deepgram endpointing config | Deepgram | High | ✅ Round 1 |
| Round 1 fix never deployed to DGX | Whisper-remote | **Critical** | ✅ Round 2 — deployed |
| TTS echo (acoustic feedback through mic) | Both | Low (not active) | N/A |

---

## 7. Fixes Implemented (Round 2)

### Fix 1: 5-layer hallucination filter (`whisper_remote_stt.py`)

Applied in sequence per segment:

1. **Duration gate** (`min_segment_duration_s=0.15`): Drop segments shorter than 150ms. This single gate eliminates the entire "I'm sorry × 53" flood — each segment is ~0.087s, all caught.

2. **`no_speech_prob` gate** (`no_speech_threshold=0.35`): Lowered from 0.5. Whisper hallucinations at the fallback temperature stage often have `no_speech_prob` in the 0.35–0.50 range.

3. **Compression ratio gate** (`compression_ratio_threshold=2.4`): Drop if `compression_ratio > 2.4`. Repetitive hallucinated text has a very high compression ratio. This is Whisper's own internal threshold.

4. **Known phrase blocklist**: Exact match (case-insensitive, strip trailing punctuation) against "i'm sorry", "thank you", "thanks for watching", dash-prefixed variants, etc.

5. **Intra-segment repetition**: Regex detects "PHRASE... PHRASE" patterns within a single segment's text.

Additionally:
- **Cross-call deduplication**: `_last_text` tracks the previous emission; identical text is dropped
- **Fallback path filtering**: The plain-text fallback (no segments returned) now applies the blocklist before yielding
- **Deployed**: `git pull` + `docker compose build agent-gateway` + `docker compose up -d agent-gateway` executed on DGX 2026-03-25

### Fix 2: Round 1 deployment (completed with Round 2)

The Round 1 changes (energy gate, Deepgram endpointing, `no_speech_prob` filter) were in the codebase but not deployed. The Round 2 deployment pulled all of these to DGX simultaneously.

---

## 8. Testing the Fix

To verify the phantom words are resolved:
1. Join a meeting, say nothing for 15–20 seconds (several Whisper windows)
2. No transcript should appear
3. Say "testing" clearly once
4. Transcript should show "testing" (or similar) with no phantom words before it

To confirm the filters are working, check DGX logs:
```bash
ssh dgx 'docker compose -f ~/convene-ai/docker-compose.yml logs agent-gateway | grep "dropped"'
```
Should show lines like: `"Whisper yielded 0 segments, dropped 36 — reasons: {'too_short': 36}"`

To confirm the energy gate is working:
- Open browser devtools → Network → WS tab
- While silent, the WebSocket should send very few messages (only those above the energy threshold)
- While speaking, messages should flow freely

---

## 9. Future Improvements (if problems persist)

If hallucinations still appear after these fixes:

1. **Server-side VAD before Whisper**: Add Silero VAD or py-webrtcvad to gate the audio buffer before sending to Whisper. Only transmit audio where VAD has confirmed speech activity. This prevents Whisper from ever seeing silent/noise-only windows.

2. **Raise energy gate threshold**: Increase RMS threshold from 0.01 to 0.02 or 0.03 to reject more ambient noise. Risk: may clip quiet speakers.

3. **Increase transcription interval**: Increase from 5s to 8s. Longer windows give Whisper more context, reducing hallucinations. Tradeoff: higher latency.

4. **Switch to Deepgram for all tiers**: Deepgram's streaming model doesn't have this fallback temperature issue. It's purpose-built for real-time transcription and uses its own VAD internally.
