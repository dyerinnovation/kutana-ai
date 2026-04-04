# Infrastructure Health Check — Local Desktop Task

> Local version. Runs every 6 hours with direct SSH access.

---

## Process

1. SSH to DGX and check health:
   ```bash
   ssh dgx 'kubectl get pods -n kutana'
   ssh dgx 'kubectl get nodes'
   ssh dgx 'df -h /'
   ssh dgx 'free -h'
   ssh dgx 'uptime'
   ```

2. Evaluate:
   - **Healthy:** All pods Running, node Ready, disk < 80%, SSH succeeded
   - **Unhealthy:** Any pod not Running, node NotReady, disk > 80%, SSH failed, load > 8

3. Write results:
   - **Healthy:** Overwrite `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Infrastructure/health-check.md` with one-liner status + timestamp
   - **Unhealthy:** Write detailed findings to health-check.md AND alert Jonathan

---

## Hard rules

- Never modify code, configs, or infrastructure. Read-only.
- Never restart services. Report only.
- Keep quiet when healthy.
