#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Ensure project root is on sys.path so we can import neo4j_utils
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from neo4j_utils import check_neo4j_connection, get_callers, get_callees
except Exception:
    check_neo4j_connection = None  # type: ignore
    get_callers = None  # type: ignore
    get_callees = None  # type: ignore

MODEL_NAME = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "code_memory")


def search_qdrant(query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=top_k,
        with_payload=True,
    )

    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append({
            "score": point.score,
            "symbol": payload.get("symbol"),
            "type": payload.get("type"),
            "file_path": payload.get("file_path", "-"),
            "code": payload.get("code") or "",
        })
    return results


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def build_mermaid(symbol: str, callers: List[str], callees: List[str]) -> str:
    # Simple left-to-right graph with callers on the left and callees on the right
    lines = ["graph LR", f"  target[\"{symbol}\"]"]
    for c in callers:
        lines.append(f"  caller_{abs(hash(c))}([\"{c}\"]) --> target")
    for c in callees:
        lines.append(f"  target --> callee_{abs(hash(c))}([\"{c}\"]) ")
    return "\n".join(lines)


def render_html(query: str, rows: List[Dict[str, Any]], out_path: str) -> None:
    # Basic, self-contained HTML with Mermaid for graphs
    head = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Search Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', Arial, sans-serif; margin: 16px; }}
    .result {{ border: 1px solid #e2e2e2; border-radius: 8px; padding: 12px; margin-bottom: 16px; }}
    .meta {{ font-size: 12px; color: #666; margin-bottom: 8px; }}
    pre {{ background: #0b1021; color: #f2f2f2; padding: 12px; border-radius: 6px; overflow: auto; }}
    code {{ white-space: pre; }}
    .title {{ font-weight: 600; font-size: 16px; margin-bottom: 6px; }}
    .score {{ color: #555; }}
    .section-label {{ font-weight: 600; margin: 10px 0 6px; }}
  </style>
  <script type=\"module\" src=\"https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs\"></script>
  <script>mermaid.initialize({{ startOnLoad: true, securityLevel: 'loose' }});</script>
</head>
<body>
  <h1>Semantic Search Report</h1>
  <div class=\"meta\">Query: <b>{html_escape(query)}</b></div>
"""

    body_parts = []
    for i, r in enumerate(rows, 1):
        title = f"{r['type']} · {r['symbol']}"
        meta = f"File: {r['file_path']} · Score: {r['score']:.4f}"
        code_snippet = html_escape("\n".join((r.get('code') or '').splitlines()[:60]))
        mermaid = r.get('mermaid')
        graph_block = f"<pre class=\"mermaid\">\n{html_escape(mermaid)}\n</pre>" if mermaid else "<div class=\"meta\">No graph context</div>"
        body_parts.append(
            f"""
<div class=\"result\">
  <div class=\"title\">{html_escape(title)}</div>
  <div class=\"meta\">{html_escape(meta)}</div>
  <div class=\"section-label\">Code</div>
  <pre><code>{code_snippet}</code></pre>
  <div class=\"section-label\">Graph</div>
  {graph_block}
</div>
"""
        )

    tail = "</body>\n</html>\n"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(head)
        for part in body_parts:
            f.write(part)
        f.write(tail)


def main():
    p = argparse.ArgumentParser(description="Generate an HTML report with code and graph context")
    p.add_argument("query", type=str)
    p.add_argument("-k", "--top_k", type=int, default=10)
    p.add_argument("-o", "--out", type=str, default="search_report.html")
    p.add_argument("--no-graph", action="store_true", help="Do not query Neo4j for graph context")
    args = p.parse_args()

    print("Loading embedding model...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)
    q_emb = model.encode(args.query).tolist()

    print("Searching Qdrant...", file=sys.stderr)
    top = search_qdrant(q_emb, args.top_k)
    if not top:
        print("No Qdrant matches found. Have you run the indexer?", file=sys.stderr)
        sys.exit(1)

    # Optionally add Mermaid graphs
    rows = []
    neo4j_enabled = os.getenv("NEO4J_ENABLED", "true").lower() not in {"0", "false", "no"}
    can_graph = (not args.no_graph) and check_neo4j_connection and neo4j_enabled and check_neo4j_connection()

    for idx, r in enumerate(top, 1):
        entry = dict(r)
        if can_graph:
            name = str(r.get('symbol') or '')
            try:
                callees = get_callees(name, limit=12) or []
                callers = get_callers(name, limit=12) or []
                entry['mermaid'] = build_mermaid(name, callers, callees)
            except Exception as e:
                entry['mermaid'] = None
        else:
            entry['mermaid'] = None
        rows.append(entry)

    print(f"Writing report: {args.out}", file=sys.stderr)
    render_html(args.query, rows, args.out)


if __name__ == "__main__":
    main()
