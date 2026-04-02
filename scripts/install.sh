#!/usr/bin/env bash
# Kutana CLI Installer
# Usage: curl -LsSf https://kutana.ai/install.sh | bash
set -euo pipefail

KUTANA_HOME="${KUTANA_HOME:-$HOME/.kutana}"
REPO_URL="https://github.com/dyerinnovation/kutana-ai.git"
REPO_DIR="$KUTANA_HOME/src"

info() { printf "\033[0;34m==>\033[0m %s\n" "$1"; }
success() { printf "\033[0;32m==>\033[0m %s\n" "$1"; }
error() { printf "\033[0;31merror:\033[0m %s\n" "$1" >&2; exit 1; }

# ── Prerequisites ──────────────────────────────────────────────────
info "Checking prerequisites..."

command -v git >/dev/null 2>&1 || error "git is required but not installed. Install it first: https://git-scm.com"

if command -v uv >/dev/null 2>&1; then
    info "Found uv: $(uv --version)"
else
    info "uv not found — installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null 2>&1 || error "uv installation failed. Install manually: https://docs.astral.sh/uv/"
    success "uv installed: $(uv --version)"
fi

# ── Clone or update repo ──────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
    info "Updating existing Kutana source..."
    git -C "$REPO_DIR" pull --quiet
else
    info "Cloning Kutana AI repository..."
    mkdir -p "$KUTANA_HOME"
    git clone --quiet "$REPO_URL" "$REPO_DIR"
fi

# ── Install CLI ───────────────────────────────────────────────────
info "Installing Kutana CLI..."
uv tool install --force -e "$REPO_DIR/services/cli"

# ── Verify ────────────────────────────────────────────────────────
if command -v kutana >/dev/null 2>&1; then
    success "Kutana CLI installed successfully!"
    echo ""
    echo "  kutana --help        Show available commands"
    echo "  kutana login         Authenticate with your Kutana instance"
    echo "  kutana meetings      List your meetings"
    echo ""
    echo "Source: $REPO_DIR"
else
    # uv tool install puts binaries in ~/.local/bin
    success "Kutana CLI installed to ~/.local/bin/kutana"
    echo ""
    echo "Add to your PATH if not already:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run: kutana --help"
fi
