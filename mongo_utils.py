from pymongo import MongoClient
import os
import hashlib
from typing import Optional, Dict, Any

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["code_index"]
collection = db["code_memory"]
file_hashes = db["file_hashes"]

def calculate_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_file_hash(file_path: str) -> Optional[str]:
    """Get the stored hash of a file if it exists."""
    result = file_hashes.find_one({"file_path": file_path})
    return result["hash"] if result else None

def update_file_hash(file_path: str, file_hash: str) -> None:
    """Update the stored hash for a file."""
    file_hashes.update_one(
        {"file_path": file_path},
        {"$set": {"hash": file_hash}},
        upsert=True
    )

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
    collection.insert_one(fragment)
