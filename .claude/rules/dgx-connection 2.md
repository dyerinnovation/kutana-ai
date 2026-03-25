# DGX Spark Connection Rules

All Docker containers, tests, and heavy compute run on the DGX Spark — not the local Mac.

**Regular commands (no password):**
```bash
ssh dgx '<command>'
scp local.txt dgx:~/path/        # copy TO DGX
scp dgx:~/path/file.txt ./       # copy FROM DGX
```

**Sudo commands (pipe password for sudo only):**
```bash
ssh dgx 'echo JDf33nawm3! | sudo -S <command>'
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -A'
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml /home/jondyer3/.local/bin/helm list -A'
```

- **Container runtime:** containerd — import via `sudo k3s ctr images import <file>`
- **Cluster URLs:** `convene.spark-b0f2.local` — use `aiohttp` not `httpx` for mDNS
- See `internal-docs/architecture/patterns/dgx-spark-ssh.md` for full patterns.
