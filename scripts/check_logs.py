#!/usr/bin/env python3
"""Convene AI infrastructure and log health checker.

Checks Docker container health, PostgreSQL, Redis, and Redis Streams.
Prints a summary report to stdout and optionally saves to a file.

Usage:
    python scripts/check_logs.py
    python scripts/check_logs.py --output docs/cowork-tasks/cowork-task-output/
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def check_docker_compose() -> dict[str, str]:
    """Check docker compose service status."""
    rc, out, err = run_cmd(["docker", "compose", "ps", "--format", "json"])
    if rc != 0:
        return {"docker": f"❌ docker compose not available: {err}"}

    results = {}
    if not out:
        results["docker"] = "⚠️ No containers running"
        return results

    for line in out.strip().split("\n"):
        try:
            container = json.loads(line)
            name = container.get("Service", container.get("Name", "unknown"))
            state = container.get("State", "unknown")
            health = container.get("Health", "")

            if state == "running":
                if health == "unhealthy":
                    results[name] = "⚠️ Running but unhealthy"
                else:
                    results[name] = "✅ Running"
            elif state == "restarting":
                results[name] = "❌ Restarting (crash loop)"
            elif state == "exited":
                results[name] = "❌ Exited"
            else:
                results[name] = f"⚠️ {state}"
        except json.JSONDecodeError:
            continue

    return results


def check_postgres() -> tuple[str, str]:
    """Check PostgreSQL connectivity."""
    rc, out, err = run_cmd(
        ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "convene"]
    )
    if rc == 0:
        return "✅", "Accepting connections"
    return "❌", f"Not ready: {err or out}"


def check_redis() -> tuple[str, str]:
    """Check Redis connectivity and basic stats."""
    rc, out, _ = run_cmd(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "ping"]
    )
    if rc != 0 or out != "PONG":
        return "❌", "Not responding to PING"

    # Get memory info
    rc, mem_out, _ = run_cmd(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "info", "memory"]
    )
    memory = "unknown"
    if rc == 0:
        for line in mem_out.split("\n"):
            if line.startswith("used_memory_human:"):
                memory = line.split(":")[1].strip()
                break

    # Get client count
    rc, client_out, _ = run_cmd(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "info", "clients"]
    )
    clients = "unknown"
    if rc == 0:
        for line in client_out.split("\n"):
            if line.startswith("connected_clients:"):
                clients = line.split(":")[1].strip()
                break

    notes = f"Memory: {memory}, Clients: {clients}"

    # Warn on high memory or client count
    try:
        client_count = int(clients)
        if client_count > 50:
            return "⚠️", f"{notes} — high client count"
    except ValueError:
        pass

    return "✅", notes


def check_redis_streams() -> tuple[str, str]:
    """Check Redis Streams health."""
    rc, out, _ = run_cmd(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "XLEN", "meeting_events"]
    )
    if rc != 0:
        return "⚠️", "Stream 'meeting_events' not found (may be normal if no meetings run)"

    try:
        stream_len = int(out)
    except ValueError:
        return "⚠️", f"Unexpected XLEN output: {out}"

    if stream_len > 10000:
        return "⚠️", f"Stream length {stream_len} — possible consumer lag"

    # Check consumer groups
    rc, groups_out, _ = run_cmd(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "XINFO", "GROUPS", "meeting_events"]
    )

    return "✅", f"Stream length: {stream_len}"


def generate_report(
    docker_status: dict[str, str],
    pg_status: tuple[str, str],
    redis_status: tuple[str, str],
    streams_status: tuple[str, str],
) -> str:
    """Generate a markdown health report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# Log Monitor Report — {date_str}",
        f"\n**Generated:** {now}",
        "",
        "## Infrastructure Health",
        "",
        "| Service | Status | Notes |",
        "|---------|--------|-------|",
        f"| PostgreSQL | {pg_status[0]} | {pg_status[1]} |",
        f"| Redis | {redis_status[0]} | {redis_status[1]} |",
    ]

    for svc, status in docker_status.items():
        lines.append(f"| Docker: {svc} | {status} | |")

    lines.extend([
        "",
        "## Application Health",
        "",
        "| Check | Status | Notes |",
        "|-------|--------|-------|",
        f"| Redis Streams | {streams_status[0]} | {streams_status[1]} |",
        "",
    ])

    # Collect alerts
    alerts = []
    if "❌" in pg_status[0]:
        alerts.append(f"- **PostgreSQL down:** {pg_status[1]}")
    if "❌" in redis_status[0]:
        alerts.append(f"- **Redis down:** {redis_status[1]}")
    for svc, status in docker_status.items():
        if "❌" in status:
            alerts.append(f"- **{svc}:** {status}")
    if "⚠️" in streams_status[0]:
        alerts.append(f"- **Redis Streams:** {streams_status[1]}")

    if alerts:
        lines.append("## Alerts")
        lines.append("")
        lines.extend(alerts)
    else:
        lines.append("## Alerts")
        lines.append("")
        lines.append("No alerts. All systems healthy.")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convene AI health checker")
    parser.add_argument(
        "--output",
        type=str,
        help="Directory to save the report (e.g. docs/cowork-tasks/cowork-task-output/)",
    )
    args = parser.parse_args()

    print("Checking Convene AI infrastructure health...\n")

    docker_status = check_docker_compose()
    pg_status = check_postgres()
    redis_status = check_redis()
    streams_status = check_redis_streams()

    report = generate_report(docker_status, pg_status, redis_status, streams_status)
    print(report)

    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output_file = output_dir / f"log-monitor-{date_str}.md"
        output_file.write_text(report)
        print(f"\nReport saved to {output_file}")


if __name__ == "__main__":
    main()
