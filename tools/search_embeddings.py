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
                "code": doc.get("code"),
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="Search similar code fragments using embeddings")
    parser.add_argument("query", type=str, help="Natural language or code-like query")
    parser.add_argument("-k", "--top_k", type=int, default=10, help="How many results to return")
    parser.add_argument("--show-code", action="store_true", help="Show a prefix of the code (if available)")
    parser.add_argument("--with-graph", action="store_true", help="Show callers/callees from Neo4j for top 5 matches")
    args = parser.parse_args()

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

    # Pretty print
    print("RESULTS (top {}):".format(args.top_k))
    print("SCORE    TYPE     SYMBOL                                                   FILE")
    print("-" * 110)
    for idx, r in enumerate(top, 1):
        print(f"{r['score']:.4f}  {r['type']:<8} {str(r['symbol'])[:55]:<55} {str(r['file_path'])[:40]}")
        if args.show_code:
            code = r.get('code')
            if code:
                snippet = code.strip().splitlines()[:8]
                for line in snippet:
                    print(f"    {line}")
                if len(code.strip().splitlines()) > 8:
                    print("    ...")
            else:
                print("    [no code stored for this fragment]")

        # Graph context for top 5 matches
        if args.with_graph and idx <= 5 and get_callers and get_callees:
            neo4j_enabled = os.getenv("NEO4J_ENABLED", "true").lower() not in {"0", "false", "no"}
            if neo4j_enabled and check_neo4j_connection and check_neo4j_connection():
                name = str(r.get('symbol') or '')
                try:
                    callees = get_callees(name, limit=10) or []
                    callers = get_callers(name, limit=10) or []
                    if callees or callers:
                        print("    Graph context:")
                        if callers:
                            print("      <- callers:")
                            for c in callers[:10]:
                                print(f"         - {c}")
                        if callees:
                            print("      -> calls:")
                            for c in callees[:10]:
                                print(f"         - {c}")
                except Exception as e:
                    print(f"    [graph lookup error: {e}]")

if __name__ == "__main__":
    main()
