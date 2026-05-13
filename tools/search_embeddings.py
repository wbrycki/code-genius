#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List, Dict, Any

from pymongo import MongoClient
import numpy as np
from sentence_transformers import SentenceTransformer

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
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "code_index")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "code_memory")


# ----------------------------
# CORE
# ----------------------------

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def load_embeddings(col) -> List[Dict[str, Any]]:
    cursor = col.find({}, {
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
        if isinstance(emb, list) and emb:
            results.append({
                "symbol": doc.get("symbol"),
                "type": doc.get("type"),
                "file_path": doc.get("file_path", "-"),
                "embedding": np.array(emb, dtype=np.float32),
                "code": doc.get("code"),
            })
    return results


# ----------------------------
# FORMATTER
# ----------------------------

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
                for line in code.splitlines()[:6]:
                    print(f"    {line}")
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
    args = parser.parse_args()

    print("Loading model...", file=sys.stderr)
    model = SentenceTransformer(MODEL_NAME)

    q_emb = np.array(model.encode(args.query), dtype=np.float32)

    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION_NAME]

    print("Loading embeddings...", file=sys.stderr)
    items = load_embeddings(col)

    if not items:
        print("No embeddings found")
        sys.exit(1)

    scored = []
    for it in items:
        scored.append({
            "score": cosine_sim(q_emb, it["embedding"]),
            **{k: v for k, v in it.items() if k != "embedding"},
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:args.top_k]

    format_results(top, args)


if __name__ == "__main__":
    main()