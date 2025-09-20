#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List, Dict, Any

from pymongo import MongoClient
import numpy as np
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
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "code_index")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "code_memory")


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def load_embeddings(col) -> List[Dict[str, Any]]:
    cursor = col.find({}, projection={
        "_id": 0,
        "symbol": 1,
        "type": 1,
        "file_path": 1,
        "embedding": 1,
        "code": 1,
    })
    results = []
    for doc in cursor:
        emb = doc.get("embedding")
        if isinstance(emb, list) and len(emb) > 0:
            results.append({
                "symbol": doc.get("symbol"),
                "type": doc.get("type"),
                "file_path": doc.get("file_path", "-"),
                "embedding": np.array(emb, dtype=np.float32),
                "code": doc.get("code") or "",
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
    q_emb = model.encode(args.query)
    q_emb = np.array(q_emb, dtype=np.float32)

    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION_NAME]

    print("Fetching embeddings from MongoDB...", file=sys.stderr)
    items = load_embeddings(col)
    if not items:
        print("No embeddings found. Have you run the indexer?", file=sys.stderr)
        sys.exit(1)

    print("Computing similarities...", file=sys.stderr)
    scored = []
    for it in items:
        score = cosine_sim(q_emb, it["embedding"])
        scored.append({
            "score": score,
            **{k: v for k, v in it.items() if k != "embedding"},
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[: args.top_k]

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
