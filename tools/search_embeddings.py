#!/usr/bin/env python3
import argparse
import fnmatch
import os
import sys
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

try:
    from pygments import highlight
    from pygments.formatters import TerminalFormatter
    from pygments.lexers import JavaLexer
except Exception:
    highlight = None
    TerminalFormatter = None
    JavaLexer = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from neo4j_utils import check_neo4j_connection, get_callers, get_callees
except Exception:
    check_neo4j_connection = None
    get_callers = None
    get_callees = None


MODEL_NAME = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "code_memory")

TEST_PATH_MARKERS = (
    "/src/test/",
    "/test/",
    "/tests/",
)

TEST_FILE_SUFFIXES = (
    "test.java",
    "tests.java",
    "it.java",
    "itcase.java",
)


# ----------------------------
# CORE
# ----------------------------

def search_qdrant(query_embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
    """Search Qdrant for similar code fragments."""
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    
    try:
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=limit,
        )
        
        results = []
        for hit in search_result.points:
            payload = hit.payload or {}
            results.append({
                "score": hit.score,
                "symbol": payload.get("symbol"),
                "type": payload.get("type"),
                "file_path": payload.get("file_path"),
                "code": payload.get("code"),
            })
        
        return results
    except Exception as e:
        print(f"Error searching Qdrant: {e}")
        return []


# ----------------------------
# FORMATTER
# ----------------------------

def is_test_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lower()
    filename = normalized.rsplit("/", 1)[-1]
    return (
        any(marker in normalized for marker in TEST_PATH_MARKERS)
        or filename.endswith(TEST_FILE_SUFFIXES)
    )


def matches_exclude_path(file_path: str, patterns: List[str]) -> bool:
    normalized = file_path.replace("\\", "/")
    for pattern in patterns:
        if pattern in normalized or fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def filter_results(results: List[Dict[str, Any]], args) -> List[Dict[str, Any]]:
    filtered = []
    for result in results:
        file_path = str(result.get("file_path") or "")

        if not args.include_tests and is_test_path(file_path):
            continue

        if args.exclude_path and matches_exclude_path(file_path, args.exclude_path):
            continue

        filtered.append(result)

    return filtered[:args.top_k]


def should_color(args) -> bool:
    if args.color == "always":
        return True
    if args.color == "never":
        return False
    return sys.stdout.isatty()


def format_code_snippet(code: str, args) -> str:
    snippet = "\n".join(code.splitlines()[:args.code_lines])

    if should_color(args) and highlight and JavaLexer and TerminalFormatter:
        snippet = highlight(snippet, JavaLexer(), TerminalFormatter()).rstrip("\n")

    return "\n".join(f"    {line}" for line in snippet.splitlines())


def format_results(top, args):
    print("\n=== RESULTS ===")
    print(f"Top {args.top_k} matches\n")

    print("SCORE    TYPE     SYMBOL                              FILE")
    print("-" * 90)

    for idx, r in enumerate(top, 1):
        print(
            f"{r['score']:.4f}  "
            f"{r['type']:<8} "
            f"{str(r['symbol'])[:35]:<35} "
            f"{str(r['file_path'])[:30]}"
        )

        # code preview
        if args.show_code:
            code = r.get("code")
            if code:
                print("\n    ── snippet ──")
                print(format_code_snippet(code, args))
                print()

        # graph context
        if args.with_graph and idx <= 5:
            print_graph_context(r)


def print_graph_context(r):
    if not (check_neo4j_connection and get_callers and get_callees):
        return

    if not check_neo4j_connection():
        return

    name = str(r.get("symbol") or "")

    try:
        callers = get_callers(name, limit=5) or []
        callees = get_callees(name, limit=5) or []

        if callers or callees:
            print("    ── graph ──")

            if callers:
                print("    <- callers:")
                for c in callers:
                    print(f"       {c}")

            if callees:
                print("    -> calls:")
                for c in callees:
                    print(f"       {c}")

            print()

    except Exception:
        pass


# ----------------------------
# MAIN
# ----------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("-k", "--top_k", type=int, default=10)
    parser.add_argument("--show-code", action="store_true")
    parser.add_argument("--with-graph", action="store_true")
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test files in search results. By default tests are excluded.",
    )
    parser.add_argument(
        "--exclude-path",
        action="append",
        default=[],
        help="Exclude paths containing or matching this glob. Can be used multiple times.",
    )
    parser.add_argument(
        "--candidate-multiplier",
        type=int,
        default=8,
        help="Fetch extra Qdrant candidates before local path filtering.",
    )
    parser.add_argument("--code-lines", type=int, default=8)
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Syntax highlighting for --show-code output.",
    )
    args = parser.parse_args()

    print("Loading model...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)

    q_emb = model.encode(args.query).tolist()

    print("Searching Qdrant...", file=sys.stderr)
    candidate_limit = max(args.top_k, args.top_k * args.candidate_multiplier)
    results = filter_results(search_qdrant(q_emb, limit=candidate_limit), args)

    if not results:
        print("No results found")
        sys.exit(1)

    format_results(results, args)


if __name__ == "__main__":
    main()
