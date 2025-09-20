#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Ensure venv and deps
"$SCRIPT_DIR/setup.sh" >/dev/null
source "$REPO_ROOT/.venv/bin/activate"

# Load .env if exists
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$REPO_ROOT/.env"
  set +a
fi

# Purge MongoDB
python "$REPO_ROOT/tools/clear_mongo.py"

# Purge Neo4j
python "$REPO_ROOT/tools/clear_neo4j.py"

echo "All stores purged. You can now run a full re-scan:"
echo "  scripts/run.sh --full-rescan"
