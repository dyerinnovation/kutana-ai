---
globs: ["packages/**/*.py", "services/**/*.py"]
---

# Python Rules

- **Python 3.12+** — use modern syntax (match/case, `X | Y` unions, `typing.Self`).
- **uv only** — use `uv add` / `uv add --dev`. Never `pip install` or `poetry`.
- **ruff** for formatting and linting. Run `ruff format` then `ruff check` before committing.
- **mypy strict** — no `# type: ignore` without an inline explanation.
- **`async def`** for all I/O. No blocking calls in async paths.
- Type-hint every function signature and return value.
- Docstrings on public methods (Google style).
- Tests in `tests/` subdirectory of each package/service.
- File naming: snake_case. Models in `models/`, ABCs in `interfaces/`, providers in `providers/`.
- See `claude_docs/UV_Best_Practices.md` and `claude_docs/PYTHONPATH_Workaround.md`.
