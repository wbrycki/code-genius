from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["code_index"]
collection = db["code_memory"]

def insert_fragment(fragment):
    collection.insert_one(fragment)
