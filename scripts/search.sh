#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Ensure environment and deps are ready
"$SCRIPT_DIR/setup.sh" >/dev/null

# Load env vars from .env if present
if [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "$REPO_ROOT/.env" | xargs -I {} echo {})
fi

# Activate venv
source "$REPO_ROOT/.venv/bin/activate"

if [ "$#" -lt 1 ]; then
  echo "Usage: scripts/search.sh \"<query>\" [-k TOP_K] [--show-code]" >&2
  exit 1
fi

python "$REPO_ROOT/tools/search_embeddings.py" "$@"
