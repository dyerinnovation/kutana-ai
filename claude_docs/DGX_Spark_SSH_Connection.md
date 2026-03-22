# DGX Spark SSH Connection Patterns

## Credentials
- **Host:** `spark-b0f2.local`
- **User:** `jondyer3`
- **Password:** stored as `DGX_PASSWORD` in `.env` (never hardcode it)
- **SSH alias:** `spark-b0f2` (configured in `~/.ssh/config` via NVIDIA Sync)

## Basic Connection
```bash
# Interactive shell
ssh jondyer3@spark-b0f2.local

# Single command (non-sudo)
ssh jondyer3@spark-b0f2.local '<command>'
```

## Sudo Commands via sshpass
Use `sshpass` to pass the password non-interactively for commands requiring sudo:

```bash
# Load DGX_PASSWORD from .env first, then:
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local 'echo '"$DGX_PASSWORD"' | sudo -S <command>'
```

**Critical: always use single quotes around the remote command** — the `!` character in the password is interpreted by the local bash shell if the command string is double-quoted.

Safe pattern (sourcing .env inline):
```bash
# Source .env and run sudo command
export $(grep -v '^#' .env | xargs)
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local 'echo '"$DGX_PASSWORD"' | sudo -S <command>'
```

## Kubernetes Commands (kubectl / helm)
K3s requires both `sudo` and an explicit `KUBECONFIG` env var (sudo drops the environment):

```bash
# kubectl
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local \
  'echo '"$DGX_PASSWORD"' | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -A'

# helm (must use full path — not in default PATH)
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local \
  'echo '"$DGX_PASSWORD"' | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm list -A'
```

Key facts:
- **KUBECONFIG:** `/etc/rancher/k3s/k3s.yaml` — always pass explicitly via `sudo env KUBECONFIG=...`
- **Helm path:** `/home/jondyer3/.local/bin/helm` — `sudo env` does not inherit PATH, always use the full path
- **Container runtime:** `containerd` (not Docker) — import images via `sudo k3s ctr images import <file>`

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

# Copy to Spark
scp myimage.tar jondyer3@spark-b0f2.local:~/

# Import on Spark
sshpass -p "$DGX_PASSWORD" ssh jondyer3@spark-b0f2.local \
  'echo '"$DGX_PASSWORD"' | sudo -S k3s ctr images import ~/myimage.tar'
```

## Gotchas
1. **`!` in passwords** — single-quote the remote command string to prevent local shell expansion
2. **sudo drops env vars** — always use `sudo env KUBECONFIG=...` not `sudo kubectl`
3. **Helm not in sudo PATH** — always use `/home/jondyer3/.local/bin/helm`
4. **Non-interactive SSH** — `.bashrc` and `.bash_profile` are not sourced; use full paths or set PATH explicitly
5. **mDNS `.local` hostname** — use `aiohttp` (not `httpx`) for programmatic HTTP requests to `spark-b0f2.local`; httpx lacks Happy Eyeballs and hangs on IPv6 link-local resolution (see memory notes)

## SSH Config
The NVIDIA Sync app manages an SSH key for passwordless access. Config in `~/.ssh/config`:
```
Host spark-b0f2
    HostName spark-b0f2.local
    User jondyer3
    IdentityFile "/Users/jonathandyer/Library/Application Support/NVIDIA/Sync/config/nvsync.key"
```
