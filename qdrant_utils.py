import os
import hashlib
import uuid
from typing import Optional, Dict, Any, List
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

COLLECTION_NAME = "code_memory"
FILE_HASHES_COLLECTION = "file_hashes"

# Embedding dimension for all-MiniLM-L6-v2
VECTOR_SIZE = 384
UPSERT_BATCH_SIZE = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", "64"))


def _stable_point_id(*parts: str) -> str:
    """Return a deterministic UUID string accepted by Qdrant as a point id."""
    key = ":".join(parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"code-genius:{key}"))


def init_collections():
    """Initialize Qdrant collections if they don't exist."""
    # Code embeddings collection
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION_NAME}")

    # File hashes collection (using vectors as dummy, storing only payload)
    try:
        client.get_collection(FILE_HASHES_COLLECTION)
    except Exception:
        client.create_collection(
            collection_name=FILE_HASHES_COLLECTION,
            vectors_config=VectorParams(size=1, distance=Distance.COSINE),
        )
        print(f"Created collection: {FILE_HASHES_COLLECTION}")


def calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_file_hash(file_path: str) -> Optional[str]:
    """Get the stored hash of a file if it exists."""
    try:
        results = client.scroll(
            collection_name=FILE_HASHES_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="file_path",
                        match=MatchValue(value=file_path),
                    )
                ]
            ),
            limit=1,
        )
        if results[0]:
            return results[0][0].payload.get("hash")
    except Exception as e:
        print(f"Error getting file hash: {e}")
    return None


def update_file_hash(file_path: str, file_hash: str) -> None:
    """Update the stored hash for a file."""
    try:
        # Delete existing entry if any
        client.delete(
            collection_name=FILE_HASHES_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="file_path",
                        match=MatchValue(value=file_path),
                    )
                ]
            ),
        )
        
        # Insert new entry
        client.upsert(
            collection_name=FILE_HASHES_COLLECTION,
            points=[
                PointStruct(
                    id=_stable_point_id("file_hash", file_path),
                    vector=[0.0],  # Dummy vector
                    payload={
                        "file_path": file_path,
                        "hash": file_hash,
                    },
                )
            ],
        )
    except Exception as e:
        print(f"Error updating file hash: {e}")


def is_file_unchanged(file_path: str) -> bool:
    """Check if a file has been modified since last scan."""
    if not os.path.exists(file_path):
        return False
        
    stored_hash = get_file_hash(file_path)
    if not stored_hash:
        return False
        
    current_hash = calculate_file_hash(file_path)
    return stored_hash == current_hash


def insert_fragment(fragment: Dict[str, Any]) -> None:
    """Insert a code fragment into the database."""
    try:
        embedding = fragment.get("embedding")
        if embedding is None:
            print(f"Warning: No embedding for fragment {fragment.get('symbol')}")
            return
        
        point_id = _stable_point_id(
            "fragment",
            fragment.get("type", ""),
            fragment.get("symbol", ""),
            fragment.get("file_path", ""),
        )
        
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "type": fragment.get("type"),
                        "symbol": fragment.get("symbol"),
                        "file_path": fragment.get("file_path"),
                        "code": fragment.get("code"),
                        "calls": fragment.get("calls", []),
                    },
                )
            ],
        )
    except Exception as e:
        print(f"Error inserting fragment {fragment.get('symbol')}: {e}")


def batch_insert_fragments(fragments: List[Dict[str, Any]]) -> None:
    """Insert multiple code fragments in a batch."""
    if not fragments:
        return
    
    points = []
    for fragment in fragments:
        embedding = fragment.get("embedding")
        if embedding is None:
            continue
        
        point_id = _stable_point_id(
            "fragment",
            fragment.get("type", ""),
            fragment.get("symbol", ""),
            fragment.get("file_path", ""),
        )
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "type": fragment.get("type"),
                    "symbol": fragment.get("symbol"),
                    "file_path": fragment.get("file_path"),
                    "code": fragment.get("code"),
                    "calls": fragment.get("calls", []),
                },
            )
        )
    
    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        chunk = points[start:start + UPSERT_BATCH_SIZE]
        try:
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=chunk,
            )
        except Exception as e:
            end = start + len(chunk)
            print(f"Error inserting Qdrant points {start + 1}-{end}: {e}")
