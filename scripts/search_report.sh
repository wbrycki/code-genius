#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

"$SCRIPT_DIR/setup.sh" >/dev/null

# Load env
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$REPO_ROOT/.env"
  set +a
fi

source "$REPO_ROOT/.venv/bin/activate"

if [ "$#" -lt 1 ]; then
  echo "Usage: scripts/search_report.sh \"<query>\" [-k TOP_K] [-o out.html] [--no-graph] [--open|--no-open]" >&2
  exit 1
fi

# Extract optional --open and output path from args without altering Python tool args
OPEN_AFTER=true
OUT_FILE="search_report.html"

PARSED_ARGS=()
skip_next=false
for ((i=1; i<=$#; i++)); do
  arg="${!i}"
  if [ "$skip_next" = true ]; then
    skip_next=false
    PARSED_ARGS+=("$arg")
    continue
  fi

  case "$arg" in
    --open)
      OPEN_AFTER=true
      ;;
    --no-open)
      OPEN_AFTER=false
      ;;
    -o|--out)
      # next token is the output file
      next_index=$((i+1))
      if [ $next_index -le $# ]; then
        next_val="${!next_index}"
        OUT_FILE="$next_val"
        skip_next=true
      fi
      PARSED_ARGS+=("$arg")
      ;;
    *)
      PARSED_ARGS+=("$arg")
      ;;
  esac
done

# Run the report generator with original args (including -o/--out when provided)
python "$REPO_ROOT/tools/search_report.py" "${PARSED_ARGS[@]}"

# Resolve OUT_FILE to absolute path
case "$OUT_FILE" in
  /*) OUT_ABS="$OUT_FILE" ;;
  *) OUT_ABS="$REPO_ROOT/$OUT_FILE" ;;
esac

echo "Report generated: $OUT_ABS"
echo "Open in browser: file://$OUT_ABS"

if [ "$OPEN_AFTER" = true ]; then
  # macOS: open default browser
  if command -v open >/dev/null 2>&1; then
    open "$OUT_ABS" || true
  else
    echo "(Could not auto-open: 'open' command not found)" >&2
  fi
fi
