# Fix MockTTS Missing `close()` — Summary

## Date: 2026-02-28

## Work Completed
- Added no-op `close()` method to `MockTTS` in `packages/kutana-providers/src/kutana_providers/testing.py`
- Follows existing pattern from `MockSTT.close()` in the same file
- Ruff: all checks passed
- Pytest: **149 passed, 0 failed** (up from 80 passed / 1 failed)

## Work Remaining
- None

## Lessons Learned
- When adding abstract methods to provider ABCs, all mock providers in `testing.py` must be updated too
- `uv sync --all-packages` is required before running tests that import across workspace packages
