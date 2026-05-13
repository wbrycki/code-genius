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
