# Deploy Whisper Large V3 STT on DGX Spark

## Objective
Deploy `openai/whisper-large-v3` as a self-hosted STT model on the DGX Spark (GB10 GPU) for meeting transcription. Uses vLLM serving behind an OpenAI-compatible API.

## Context
- DGX Spark has GB10 GPU with 128GB unified memory, ARM64 architecture, running K3s
- Currently serving Qwen3-30B-A3B via vLLM — must spin down first (GPU can only serve one model)
- Whisper Large V3 is ~3GB (vs Qwen's 50GB), well within capacity
- vLLM image: `nvcr.io/nvidia/vllm:26.01-py3`

## Plan Steps

### Step 0: Documentation
- [x] Create `claude_docs/DGX_Spark_Reference.md` with connection details, K8s patterns
- [x] Add reference in `CLAUDE.md`

### Step 1: Create Helm Chart
- [x] `charts/stt/Chart.yaml` — chart metadata
- [x] `charts/stt/values.yaml` — model config, resources, service
- [x] `charts/stt/templates/deployment.yaml` — vLLM pod with Whisper args
- [x] `charts/stt/templates/service.yaml` — ClusterIP service on port 8080
- [x] `charts/stt/templates/ingress.yaml` — NGINX ingress for external access

### Step 2: Spin Down Qwen
- [ ] Uninstall tgi Helm release on DGX Spark
- [ ] Verify GPU is freed

### Step 3: Download Whisper Model
- [ ] Download `openai/whisper-large-v3` to HuggingFace cache on Spark

### Step 4: Deploy STT Chart
- [ ] Copy chart to Spark (scp)
- [ ] `helm install stt` in kutana namespace

### Step 5: Verify
- [ ] Pod is Running with GPU
- [ ] `/v1/models` returns whisper-large-v3
- [ ] Audio transcription endpoint works

## Key Details
- SSH: `jondyer3@spark-b0f2.local`
- Sudo pattern: `echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml`
- Helm path: `/home/jondyer3/.local/bin/helm`
- HuggingFace cache: `/home/jondyer3/.cache/huggingface`
- Ingress host: `spark-b0f2.local`
- Ingress path: `/kutana-stt(/|$)(.*)`
