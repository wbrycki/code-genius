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
export MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-test}"

# Activate and run
source "$REPO_ROOT/.venv/bin/activate"
echo "Using REPO_FOLDER=$REPO_FOLDER"
python "$REPO_ROOT/main.py" "$@"

echo "\n=== MongoDB Summary (code_index.code_memory) ==="
python - <<'PY'
import os
from pymongo import MongoClient

uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
client = MongoClient(uri)
col = client['code_index']['code_memory']

def fmt_head(emb):
    if not isinstance(emb, list):
        return "-"
    show = emb[:5]
    return '[' + ', '.join(f"{v:.4f}" for v in show) + (" ...]" if len(emb) > 5 else "]")

try:
    total = col.count_documents({})
    print(f"Total embeddings stored: {total}")
    print("\n=== Preview: first 25 embeddings ===")
    docs = col.find({}, projection={'symbol': 1, 'type': 1, 'embedding': 1}).limit(25)
    rows = []
    for d in docs:
        emb = d.get('embedding')
        dims = len(emb) if isinstance(emb, list) else 0
        rows.append({
            'type': d.get('type', '-'),
            'symbol': (d.get('symbol') or '-')[:60],
            'dims': dims,
            'head': fmt_head(emb),
        })

    if total == 0:
        print("No embeddings found in code_memory.")
    else:
        # Print as a simple table
        print("\nTYPE     SYMBOL                                                       DIMS   HEAD")
        print("-" * 90)
        for r in rows:
            print(f"{r['type']:<8} {r['symbol']:<60} {r['dims']:>4}   {r['head']}")
except Exception as e:
    print(f"Failed to fetch embeddings preview: {e}")
PY
