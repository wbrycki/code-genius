#!/usr/bin/env python3
import os
import sys

from qdrant_client import QdrantClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from qdrant_utils import COLLECTION_NAME, FILE_HASHES_COLLECTION, init_collections


QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)


def main() -> None:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    for name in (COLLECTION_NAME, FILE_HASHES_COLLECTION):
        try:
            client.delete_collection(collection_name=name)
            print(f"Deleted Qdrant collection: {name}")
        except Exception as e:
            print(f"Collection {name} was not deleted: {e}")

    init_collections()
    print("Qdrant purge complete.")


if __name__ == "__main__":
    main()
