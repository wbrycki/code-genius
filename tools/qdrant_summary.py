#!/usr/bin/env python3
import os

from qdrant_client import QdrantClient


QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "code_memory")


def main() -> None:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    try:
        info = client.get_collection(COLLECTION_NAME)
        total = info.points_count or 0
        print(f"Total embeddings stored: {total}")
        print("\n=== Preview: first 25 embeddings ===")

        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=25,
            with_payload=True,
            with_vectors=False,
        )

        if total == 0:
            print(f"No embeddings found in {COLLECTION_NAME}.")
            return

        print("\nTYPE     SYMBOL                                                       FILE")
        print("-" * 100)
        for point in points:
            payload = point.payload or {}
            frag_type = payload.get("type", "-")
            symbol = (payload.get("symbol") or "-")[:60]
            file_path = (payload.get("file_path") or "-")[:36]
            print(f"{frag_type:<8} {symbol:<60} {file_path}")

    except Exception as e:
        print(f"Failed to fetch Qdrant preview: {e}")


if __name__ == "__main__":
    main()
