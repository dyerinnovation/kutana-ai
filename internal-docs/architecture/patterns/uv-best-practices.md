# uv Best Practices for Convene AI

## Package Management Commands

| Do | Don't |
|----|-------|
| `uv add <pkg>` | `uv pip install <pkg>` |
| `uv add --dev <pkg>` | `pip install <pkg>` |
| `uv sync --all-packages` | `uv pip list` (different resolver context) |
| `uv run <cmd>` | Activating venv manually |

## Workspace Testing

### Running Tests

```bash
# Run tests for a specific workspace member
UV_LINK_MODE=copy uv run pytest services/audio-service/tests/ -v

# Run tests scoped to a specific package's dependencies
UV_LINK_MODE=copy uv run --package audio-service pytest services/audio-service/tests/ -v

# Run all tests across the workspace
UV_LINK_MODE=copy uv run pytest -x -v
```

- All workspace members share one `.venv` and one `uv.lock`
- `uv sync --all-packages` installs all members as editable packages via `.pth` files in `site-packages/`
- `uv run` from the workspace root has access to all installed members
- Use `--package <name>` when you want to scope to a member's declared dependencies

### pytest Configuration (pyproject.toml at workspace root)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--import-mode=importlib"
```

- `--import-mode=importlib` is required for monorepos with multiple `tests/` directories — avoids `conftest.py` and `__init__.py` collision issues
- `asyncio_mode = "auto"` auto-detects async tests without per-test `@pytest.mark.asyncio` markers

### src-layout Packages

Each workspace member uses hatch build backend with src layout:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/audio_service"]
```

The editable install creates a `.pth` file (e.g. `_audio_service.pth`) in `site-packages/` containing the path to `services/audio-service/src`. Python's `site.py` reads these at startup to extend `sys.path`.

## Known Pitfalls

### macOS `UF_HIDDEN` Flag Breaks .pth Files (Python 3.13+)

**Symptom:** `ModuleNotFoundError` for all workspace member packages despite `uv sync --all-packages` succeeding.

**Root Cause:** Python 3.13 introduced a security fix ([CPython #113659](https://github.com/python/cpython/issues/113659)) that skips `.pth` files with the macOS `UF_HIDDEN` flag. If `.venv` gets the hidden flag (from Finder, Time Machine, or manual `chflags`), all `.pth` files inside inherit it and are silently ignored.

**Diagnosis:**
```bash
# Check for hidden flag
ls -lOd .venv
# Look for "hidden" in the flags column

# Confirm .pth files are being skipped
uv run python -v -c "import audio_service" 2>&1 | grep -i "skipping"
```

**Fix:**
```bash
chflags -R nohidden .venv
```

**Prevention:** Don't set hidden flags on `.venv` directories. If macOS tooling auto-hides dot-prefixed dirs, exclude `.venv`.

### UV_LINK_MODE=copy on macOS

On macOS with APFS, `uv sync` may fail with reflink errors. Always use:

```bash
UV_LINK_MODE=copy uv sync --all-packages
```

Or export it in your shell profile:
```bash
export UV_LINK_MODE=copy
```

### Never Use `uv pip` Subcommands

`uv pip install`, `uv pip list`, etc. operate in a different resolver context than `uv add`/`uv sync`. They can produce incorrect or misleading results. Always use:

- `uv add` / `uv remove` for dependency management
- `uv sync` for installing
- `uv run` for execution
