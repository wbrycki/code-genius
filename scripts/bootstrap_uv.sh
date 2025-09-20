#!/usr/bin/env bash
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  echo "uv is already installed: $(command -v uv)"
  exit 0
fi

echo "Installing uv (Rust-based Python package manager)..."
# Official installer from Astral
curl -LsSf https://astral.sh/uv/install.sh | sh

# Try to add common install directories to PATH for this session
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  echo "uv installed: $(command -v uv)"
else
  echo "uv installation completed, but 'uv' not found on PATH."
  echo "You may need to add one of the following to your shell profile (e.g. ~/.zshrc):"
  echo '  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"'
  exit 1
fi
