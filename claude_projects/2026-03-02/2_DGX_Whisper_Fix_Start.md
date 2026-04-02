# Fix DGX Spark Whisper Audio Support & Re-run E2E Test

## Context

The E2E gateway test (`scripts/test_e2e_gateway.py`) successfully connects, joins a meeting, and sends 5.86s of LibriSpeech audio through the agent gateway to the DGX Spark Whisper API. However, the Whisper endpoint at `http://spark-b0f2.local/kutana-stt/v1/audio/transcriptions` returns HTTP 500:

```json
{"error": {"message": "Please install vllm[audio] for audio support", "type": "Internal Server Error"}}
```

The NVIDIA vLLM image (`nvcr.io/nvidia/vllm:26.01-py3`) loads the Whisper model but lacks the audio processing dependencies (librosa, soundfile, scipy) needed for the `/audio/transcriptions` endpoint.

## Approach

**Inline pip install** — modify the Helm chart's deployment command to `pip install` the audio dependencies before starting `vllm serve`. This is the simplest fix: one file change, no image rebuild, no container registry needed.

Other approaches considered and rejected:
- Init container: doesn't work (can't share filesystem with main container)
- Custom Dockerfile: no Docker on Spark, `ctr` image building is cumbersome
- PostStart hook: race condition with vllm startup

## Plan

### Step 1: Modify Helm chart deployment template
**File:** `charts/stt/templates/deployment.yaml`

Change the command block from direct `vllm serve` invocation to a shell command that installs audio deps first:

```yaml
command:
  - "sh"
  - "-c"
  - >-
    pip install --no-cache-dir librosa soundfile scipy &&
    vllm serve {{ .Values.model.id }}
    --port {{ .Values.service.port }}
    {{- range .Values.vllm.extraArgs }}
    {{ . | quote }}
    {{- end }}
```

Also bump liveness probe `initialDelaySeconds` from 120 to 180 to account for extra pip install time.

### Step 2: Deploy to DGX Spark
- SCP chart to Spark
- Helm upgrade
- Watch pod restart and verify logs (pip install success -> vLLM model load -> health check passing)

### Step 3: Verify Whisper API directly
```bash
curl -X POST http://spark-b0f2.local/kutana-stt/v1/audio/transcriptions \
  -F "file=@data/input/test-speech.wav" \
  -F "model=openai/whisper-large-v3" \
  -F "response_format=verbose_json"
```

### Step 4: Re-run E2E gateway test
Start gateway with `AGENT_GATEWAY_STT_PROVIDER=whisper-remote` and run `scripts/test_e2e_gateway.py`.

### Step 5: Document results
Write `2_DGX_Whisper_Fix_End.md` summary.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `charts/stt/templates/deployment.yaml` | MODIFY | `sh -c "pip install ... && vllm serve ..."`, bump liveness probe to 180s |

## Success Criteria
`data/output/e2e_results.json` contains `transcripts_received > 0` and `combined_text` includes recognizable English text from the LibriSpeech sample.
