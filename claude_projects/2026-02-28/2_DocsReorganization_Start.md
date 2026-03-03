# Plan: Finish Post-Session Cleanup — Docs Reorganization + Verification

## Date: 2026-02-28

## Overview
Restructure `docs/cowork-tasks/` to nest output files and task description files into subdirectories, update all references, remove an unused `noqa` directive, and verify with ruff + pytest.

## Work Items

### Item A: Restructure `docs/cowork-tasks/`
1. Move `docs/cowork-task-output/` contents into `docs/cowork-tasks/cowork-task-output/`
2. Move task description files into `docs/cowork-tasks/cowork-task-descriptions/`
3. Create `GUIDE.md` in the descriptions directory
4. Update all references in README.md, SETUP_GUIDE.md, task files

### Item B: Code Fix + Verification
1. Remove unused `# noqa: PLW0603` from `deps.py:71`
2. Run ruff check
3. Run pytest

## Team Structure
- `docs-reorganizer`: File moves, GUIDE.md creation, reference updates
- `verifier`: noqa removal, ruff, pytest
