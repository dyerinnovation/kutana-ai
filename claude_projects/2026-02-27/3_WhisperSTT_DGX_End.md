# Deploy Whisper Large V3 STT on DGX Spark — Summary

## Work Completed

- Created `claude_docs/DGX_Spark_Reference.md` with connection details, K8s patterns, command patterns, and gotchas
- Added Infrastructure section to `CLAUDE.md` referencing DGX Spark docs and STT chart
- Created Helm chart at `charts/stt/` with:
  - `Chart.yaml` — chart metadata (v0.1.0)
  - `values.yaml` — vLLM image, Whisper model config, resources (32Gi limit, 1 GPU), ingress
  - `templates/deployment.yaml` — vLLM deployment with `Recreate` strategy, health probes, HF cache mount
  - `templates/service.yaml` — ClusterIP on port 8080
  - `templates/ingress.yaml` — NGINX ingress at `/kutana-stt` with rewrite
- Uninstalled Qwen/TGI Helm release from DGX Spark to free GPU
- Downloaded `openai/whisper-large-v3` model (~3GB) to HuggingFace cache on Spark
- Deployed STT chart as Helm release `stt` in `convene` namespace (revision 3)
- Verified:
  - Pod is Running (1/1 Ready) with GPU allocated
  - `curl http://spark-b0f2.local/kutana-stt/v1/models` returns `openai/whisper-large-v3`
  - Helm list shows `stt` release in `convene` namespace

## Work Remaining

- Test audio transcription endpoint with a real `.wav` file (`/v1/audio/transcriptions`)
- Integrate STT endpoint into Kutana AI audio-service (update STT provider config)
- Consider adding a WhisperSelfHosted provider in `kutana-providers` that targets this endpoint
- Set up monitoring/alerting for the STT pod
- Git commit the new files (docs + Helm chart)

## Lessons Learned

1. **NVIDIA vLLM container entrypoint**: The `nvcr.io/nvidia/vllm` container uses `nvidia_entrypoint.sh` which wraps `exec`. Passing bare `--model` args fails — must use explicit `command: ["vllm", "serve", ...]` instead of `args`.

2. **Single-GPU Recreate strategy**: With only 1 GPU, Kubernetes `RollingUpdate` strategy deadlocks — the new pod can't schedule because the old pod holds the GPU. Must use `strategy: type: Recreate` to terminate old pod first.

3. **HuggingFace CLI rename**: The `huggingface-cli` command is now just `hf` in newer `huggingface_hub` versions. Use `uvx --from huggingface_hub hf download ...`.

4. **uv/uvx on DGX Spark**: `uv` is installed at `~/.local/bin/uv` but not in the default PATH. Use full path or `uvx` for one-off tool runs.

5. **vLLM Whisper support**: vLLM 0.13.0 natively supports `WhisperForConditionalGeneration` as an encoder-decoder model. It automatically disables chunked prefill and prefix caching for this architecture.

6. **Model download time**: Whisper Large V3 (~3GB, 21 files) took ~27 minutes to download on the Spark. Plan for this when switching models.
