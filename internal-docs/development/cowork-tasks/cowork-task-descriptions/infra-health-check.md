# Infrastructure Health Check — Task Instructions

> These instructions are read and executed by the CoWork scheduled task.
> This task runs every 6 hours to monitor infrastructure health.

---

## Purpose

Check DGX Spark / K3s cluster health. Only alert if something is wrong. Keep it quiet when healthy.

---

## Process

1. SSH to DGX and run health checks:
   ```bash
   ssh dgx 'kubectl get pods -n kutana' 2>&1
   ssh dgx 'kubectl get nodes' 2>&1
   ssh dgx 'df -h /' 2>&1
   ssh dgx 'free -h' 2>&1
   ssh dgx 'uptime' 2>&1
   ```

   If SSH fails entirely, that IS the alert.

2. Evaluate health:

   **Healthy** (ALL must be true):
   - All pods in Running state
   - Node is Ready
   - Disk usage < 80%
   - Memory usage reasonable (not swapping heavily)
   - SSH succeeded

   **Unhealthy** (ANY of these):
   - Pod in CrashLoopBackOff, Error, or Pending state
   - Node NotReady
   - Disk > 80%
   - SSH failed
   - Load average > 8 (DGX Spark has 12 cores)

3. Write results:

   **If healthy:** Overwrite `/Volumes/Dev_SSD/Dyer_Innovation_Obsidian_Vault/Dyer-Innovation/Dyer Innovation/Kutana AI/Infrastructure/health-check.md` with a one-liner:
   ```markdown
   ---
   updated: {YYYY-MM-DD HH:MM}
   type: health
   ---
   All systems healthy. Pods: {count} running. Disk: {usage}%. Last checked: {timestamp}.
   ```

   **If unhealthy:** Write detailed findings to health-check.md AND send a proactive alert message to Jonathan describing exactly what's wrong and suggested remediation.

   **If vault not mounted:** Write to `internal-docs/development/cowork-tasks/cowork-task-output/HEALTH_CHECK.md` as fallback.

---

## Hard rules

- **Never modify code, configs, or infrastructure.** This task is read-only monitoring.
- **Never restart services.** Report issues, don't fix them.
- **Keep it quiet when healthy.** No alerts, no notifications — just update the health file.
- **Always write the health file.** Even if everything is healthy.
