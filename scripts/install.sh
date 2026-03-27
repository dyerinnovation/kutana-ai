#!/usr/bin/env bash
# Convene CLI Installer
# Usage: curl -LsSf https://convene.ai/install.sh | bash
set -euo pipefail

CONVENE_HOME="${CONVENE_HOME:-$HOME/.convene}"
REPO_URL="https://github.com/dyerinnovation/convene-ai.git"
REPO_DIR="$CONVENE_HOME/src"

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
    info "Updating existing Convene source..."
    git -C "$REPO_DIR" pull --quiet
else
    info "Cloning Convene AI repository..."
    mkdir -p "$CONVENE_HOME"
    git clone --quiet "$REPO_URL" "$REPO_DIR"
fi

# ── Install CLI ───────────────────────────────────────────────────
info "Installing Convene CLI..."
uv tool install --force -e "$REPO_DIR/services/cli"

# ── Verify ────────────────────────────────────────────────────────
if command -v convene >/dev/null 2>&1; then
    success "Convene CLI installed successfully!"
    echo ""
    echo "  convene --help        Show available commands"
    echo "  convene login         Authenticate with your Convene instance"
    echo "  convene meetings      List your meetings"
    echo ""
    echo "Source: $REPO_DIR"
else
    # uv tool install puts binaries in ~/.local/bin
    success "Convene CLI installed to ~/.local/bin/convene"
    echo ""
    echo "Add to your PATH if not already:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run: convene --help"
fi
