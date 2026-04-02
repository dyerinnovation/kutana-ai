# CLI Installer Design

**Status:** Implemented (Phase 1)
**Date:** 2026-03-26

## Overview

The Kutana CLI installer provides a one-liner installation experience similar to `uv`, `rustup`, and `nvm`. It handles prerequisites, cloning the repo, and installing the CLI tool.

## Installation Flow

```
curl -LsSf https://kutana.ai/install.sh | bash
```

### What the script does

1. **Check prerequisites**: Verify `git` is installed
2. **Install uv**: If `uv` is not found, install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. **Clone repo**: Clone `kutana-ai` to `~/.kutana/src/` (or `git pull` if it already exists)
4. **Install CLI**: Run `uv tool install -e ~/.kutana/src/services/cli`
5. **Verify**: Check that `kutana` command is available, print usage hints

### Directory layout

```
~/.kutana/
└── src/          # git clone of kutana-ai repo
```

The CLI binary is installed to `~/.local/bin/kutana` by `uv tool install`.

## Phases

### Phase 1 (current): Source install via uv

- Script clones the full repo and installs from source
- Requires git + uv (uv is auto-installed if missing)
- Simple, works today, mirrors dev workflow

### Phase 2: Pre-built distribution

- Publish `kutana-cli` as a PyPI package or uv package
- `uv tool install kutana-cli` without cloning the repo
- Faster install, smaller footprint

### Phase 3: Binary distribution

- Pre-built binaries for Linux x64, macOS arm64/x64
- Hosted on GitHub Releases or kutana.ai CDN
- Checksum verification built into installer
- No Python/uv dependency for end users

## Uninstall

```bash
uv tool uninstall kutana-cli
rm -rf ~/.kutana
```

## Reference

- **uv installer**: https://docs.astral.sh/uv/getting-started/installation/
- **rustup**: https://rustup.rs/ (curl | sh pattern, platform detection)
- **nvm**: https://github.com/nvm-sh/nvm (bash script, PATH management)
