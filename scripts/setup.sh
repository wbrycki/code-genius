#!/usr/bin/env bash
set -euo pipefail

# Bootstrap uv if missing
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

"$SCRIPT_DIR/bootstrap_uv.sh"

# Create virtual environment (.venv) using uv
if [ ! -d "$REPO_ROOT/.venv" ]; then
  echo "Creating virtual environment at $REPO_ROOT/.venv"
  uv venv "$REPO_ROOT/.venv"
else
  echo "Virtual environment already exists at $REPO_ROOT/.venv"
fi

# Activate and install dependencies from requirements.txt
source "$REPO_ROOT/.venv/bin/activate"
uv pip install -r "$REPO_ROOT/requirements.txt"

echo "Setup complete. To activate the environment in your shell:"
echo "  source .venv/bin/activate"
echo "Then you can run the indexer with:"
echo "  scripts/run.sh"
