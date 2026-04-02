# macOS UF_HIDDEN Flag & PYTHONPATH Workaround

## Problem

When `uv sync` installs workspace packages in editable mode, it creates `.pth` files in `.venv/lib/python3.13/site-packages/`. On macOS, the quarantine system may set the `UF_HIDDEN` flag on these files. Python 3.13 silently ignores `.pth` files with the hidden flag, causing editable packages to be unresolvable at import time.

## Detection

Check for the `hidden` flag on `.pth` files:

```bash
ls -lO .venv/lib/python3.13/site-packages/_agent_gateway.pth
```

If you see `hidden` in the flags column, the file is affected.

## Fix Options

### Option 1: Clear the hidden flag (may not work in sandboxed environments)

```bash
find .venv/lib/python3.13/site-packages -maxdepth 1 -name "*.pth" -print0 | xargs -0 chflags nohidden
```

### Option 2: Set PYTHONPATH explicitly (reliable, no system flag changes)

```bash
export PYTHONPATH=services/agent-gateway/src:services/audio-service/src:packages/kutana-core/src:packages/kutana-providers/src:packages/kutana-memory/src:services/api-server/src:services/task-engine/src:services/worker/src
```

Use this prefix when running services:

```bash
PYTHONPATH=services/agent-gateway/src:services/audio-service/src:packages/kutana-core/src:packages/kutana-providers/src:packages/kutana-memory/src:services/api-server/src:services/task-engine/src:services/worker/src .venv/bin/python -m pytest services/agent-gateway/tests/ -v
```

### Option 3: Use UV_LINK_MODE=copy (avoids .pth files entirely)

```bash
UV_LINK_MODE=copy uv sync --all-packages
```

This copies packages instead of symlinking/using `.pth` files, bypassing the issue completely.

## Recommendation

Option 3 is the most permanent fix. Option 2 is the quickest workaround for debugging. Option 1 may need to be re-applied after each `uv sync`.
