#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Ensure uv and the venv are ready and deps are installed
"$SCRIPT_DIR/setup.sh"

# Load env vars from .env if present (robustly)
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$REPO_ROOT/.env"
  set +a
fi

# Defaults if not provided
export REPO_FOLDER="${REPO_FOLDER:-$REPO_ROOT/repo_to_index}"
# Normalize REPO_FOLDER to an absolute path relative to repo root if needed
case "$REPO_FOLDER" in
  /*) : ;; # absolute already
  *) REPO_FOLDER="$REPO_ROOT/$REPO_FOLDER" ;;
esac
export REPO_FOLDER
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-test}"

# Activate and run
source "$REPO_ROOT/.venv/bin/activate"
echo "Using REPO_FOLDER=$REPO_FOLDER"
python "$REPO_ROOT/main.py" "$@"

printf "\n=== Qdrant Summary (%s) ===\n" "${COLLECTION_NAME:-code_memory}"
python "$REPO_ROOT/tools/qdrant_summary.py"
