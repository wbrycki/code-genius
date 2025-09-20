#!/usr/bin/env python3
import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "code_index")

if __name__ == "__main__":
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    collections = ["code_memory", "file_hashes"]
    for name in collections:
        col = db[name]
        result = col.delete_many({})
        print(f"Cleared {name}: deleted {result.deleted_count} documents")

    print("MongoDB purge complete.")
