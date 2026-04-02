# DGX Spark Reference

## Hardware
- **GPU:** NVIDIA GB10 Grace Blackwell
- **Memory:** 128GB unified (CPU+GPU shared)
- **Architecture:** ARM64 (aarch64)
- **OS:** Ubuntu-based NVIDIA DGX OS

## Access
- **Hostname:** `spark-b0f2.local`
- **User:** `jondyer3`
- **SSH:** `ssh jondyer3@spark-b0f2.local`

## Kubernetes (K3s)
- **Distribution:** K3s (lightweight Kubernetes)
- **Kubeconfig:** `/etc/rancher/k3s/k3s.yaml` (requires sudo)
- **Ingress:** NGINX ingress controller (built into K3s)
- **GPU Plugin:** NVIDIA device plugin for Kubernetes

### Command Pattern
All `kubectl` and `helm` commands require sudo with KUBECONFIG:

```bash
# Direct command (use DGX_PASSWORD from .env — see claude_docs/DGX_Spark_SSH_Connection.md)
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local \
  'echo '"$DGX_PASSWORD"' | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -A'

# Helm (custom install path — must use full path, not in sudo PATH)
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local \
  'echo '"$DGX_PASSWORD"' | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm list -A'
```

See `claude_docs/DGX_Spark_SSH_Connection.md` for full SSH patterns, sshpass usage, and gotchas.

### Namespaces
- `kutana` — Kutana AI services (STT, future LLM)
- `default` — K3s system components

## Model Serving
- **Image:** `nvcr.io/nvidia/vllm:26.01-py3` (NVIDIA-optimized vLLM)
- **HuggingFace Cache:** `/home/jondyer3/.cache/huggingface` (mounted as hostPath)
- **GPU Constraint:** Only one model can use the GPU at a time — must uninstall current before deploying new

### Current Deployment
- **Model:** `openai/whisper-large-v3` (~3GB) via vLLM
- **Helm Release:** `stt` in `kutana` namespace
- **API:** OpenAI-compatible at `http://spark-b0f2.local/kutana-stt/v1/`

### Previous Deployments
- Qwen3-30B-A3B via TGI (uninstalled to free GPU for Whisper)

## Ingress Patterns
NGINX ingress with path-based routing:

```yaml
annotations:
  nginx.ingress.kubernetes.io/rewrite-target: /$2
  nginx.ingress.kubernetes.io/use-regex: "true"
spec:
  rules:
    - host: spark-b0f2.local
      http:
        paths:
          - path: /kutana-stt(/|$)(.*)
            pathType: ImplementationSpecific
```

Access: `http://spark-b0f2.local/kutana-stt/v1/models`

## Tools on Spark
- `uv`/`uvx` — at `~/.local/bin/uv` (NOT in default PATH, use full path)
- `hf` — HuggingFace CLI via `uvx --from huggingface_hub hf download ...` (old `huggingface-cli` name is gone)
- `helm` — at `/home/jondyer3/.local/bin/helm`
- `kubectl` — system-installed via K3s

## Gotchas
1. **ARM64 images only** — must use aarch64-compatible container images
2. **Sudo for K8s** — always need sudo + KUBECONFIG env var
3. **Helm path** — not in default PATH, use full path `/home/jondyer3/.local/bin/helm`
4. **Single GPU** — can only serve one model at a time, must uninstall before switching
5. **hostPath volumes** — HuggingFace cache is on the host filesystem, not a PV/PVC
6. **No container registry** — images pulled directly from public registries (nvcr.io, docker.io)
7. **NVIDIA vLLM entrypoint** — must use `command: ["vllm", "serve", ...]` not bare `args: ["--model", ...]` — the nvidia_entrypoint.sh wrapper breaks with bare flags
8. **Recreate deployment strategy** — single GPU means `RollingUpdate` deadlocks; always use `strategy: type: Recreate`
9. **uv not in PATH** — use full path `~/.local/bin/uv` or `~/.local/bin/uvx`
10. **Externally-managed Python** — cannot `pip install` system-wide; use `uvx` for one-off tools
11. **vLLM audio support** — the NVIDIA vLLM image may not include `vllm[audio]` by default. The `/v1/models` endpoint will show Whisper loaded, but `/v1/audio/transcriptions` will return HTTP 500 with `"Please install vllm[audio] for audio support"`. Fix: rebuild the container image with `pip install vllm[audio]` or install at runtime in the pod
