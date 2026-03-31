# DGX Spark SSH Connection Patterns

## Credentials
- **Host:** `spark-b0f2.local`
- **User:** `jondyer3`
- **Password:** stored as `DGX_PASSWORD` in `.env` — only needed for sudo commands now
- **SSH alias:** `dgx` (key-based auth via `~/.ssh/id_dgx_spark`, no password for regular commands)
- **Also works:** `spark-b0f2`, `spark-b0f2.local`

## Basic Connection
```bash
# Interactive shell (no password)
ssh dgx

# Single command (non-sudo, no password)
ssh dgx '<command>'
```

## Sudo Commands via sshpass
sshpass is still required for commands needing sudo (sudo requires a password):

```bash
# Load DGX_PASSWORD from .env first, then:
sshpass -p "$DGX_PASSWORD" ssh dgx 'echo '"$DGX_PASSWORD"' | sudo -S <command>'
```

**Critical: always use single quotes around the remote command** — the `!` character in the password is interpreted by the local bash shell if the command string is double-quoted.

Safe pattern (sourcing .env inline):
```bash
# Source .env and run sudo command
export $(grep -v '^#' .env | xargs)
sshpass -p "$DGX_PASSWORD" ssh dgx 'echo '"$DGX_PASSWORD"' | sudo -S <command>'
```

## Kubernetes Commands (kubectl / helm)
kubectl and helm are configured locally to connect directly to the DGX Spark K3s cluster — no SSH required for cluster operations:

```bash
# kubectl (runs locally, targets DGX K3s cluster)
kubectl get pods -A
kubectl -n convene get pods

# helm (runs locally, targets DGX K3s cluster)
helm list -A
helm upgrade --install convene charts/convene -n convene --create-namespace
```

Key facts:
- **Local kubectl/helm:** configured via `~/.kube/config` to target the DGX Spark cluster directly
- **Container runtime:** `containerd` (not Docker) — import images via `k3s ctr images import <file>` on the DGX
- **Image builds still happen on DGX:** `ssh dgx 'cd ~/convene-ai && bash scripts/build_and_push.sh all'`
- **Old pattern (no longer needed):** the previous `ssh dgx 'echo PASSWORD | sudo -S env KUBECONFIG=... kubectl ...'` approach is retired

## PATH on Spark
The Spark's PATH includes non-standard locations. When running commands over SSH, the shell is non-interactive and may not source `.bashrc`. Use full paths or explicitly set PATH:

```bash
# Spark PATH includes:
$HOME/.local/bin:$HOME/.nvm/versions/node/v22.22.0/bin:$PATH

# Tools and their full paths:
# uv/uvx: ~/.local/bin/uv  (NOT in default sudo PATH)
# helm:   /home/jondyer3/.local/bin/helm
# kubectl: system PATH (via K3s install)
```

## Image Import (containerd)
Since K3s uses containerd instead of Docker, you cannot use `docker load`. Build images locally (or pull), save them as tarballs, and import:

```bash
# Save image locally
docker save myimage:tag -o myimage.tar

# Copy to Spark (key-based, no password)
scp myimage.tar dgx:~/

# Import on Spark (sudo still requires sshpass)
sshpass -p "$DGX_PASSWORD" ssh dgx \
  'echo '"$DGX_PASSWORD"' | sudo -S k3s ctr images import ~/myimage.tar'
```

## Gotchas
1. **`!` in passwords** — single-quote the remote command string to prevent local shell expansion
2. **sudo drops env vars** — always use `sudo env KUBECONFIG=...` not `sudo kubectl`
3. **Helm not in sudo PATH** — always use `/home/jondyer3/.local/bin/helm`
4. **Non-interactive SSH** — `.bashrc` and `.bash_profile` are not sourced; use full paths or set PATH explicitly
5. **mDNS `.local` hostname** — use `aiohttp` (not `httpx`) for programmatic HTTP requests to `spark-b0f2.local`; httpx lacks Happy Eyeballs and hangs on IPv6 link-local resolution (see memory notes)

## SSH Config
Key-based auth configured in `~/.ssh/config` (set up 2026-03-21):
```
Host dgx spark-b0f2 spark-b0f2.local
    HostName spark-b0f2.local
    User jondyer3
    IdentityFile ~/.ssh/id_dgx_spark
    StrictHostKeyChecking no
    ServerAliveInterval 60
    ServerAliveCountMax 3
```
The NVIDIA Sync app also has its own entry (`spark-b0f2` alias via included config) — the explicit entry above takes precedence for all three aliases.
