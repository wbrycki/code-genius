import os
from tqdm import tqdm
from parser import extract_classes_and_methods
from mongo_utils import insert_fragment
from neo4j_utils import insert_method_call
from sentence_transformers import SentenceTransformer

# -------- CONFIG --------
REPO_FOLDER = "/app/repo_to_index"
MODEL_NAME = "all-MiniLM-L6-v2"  # lightweight, fast embedding model

# -------- LOAD MODEL --------
print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)

def get_embedding(code_text):
    """Generate embedding vector using sentence-transformers."""
    return model.encode(code_text).tolist()

def main():
    all_fragments = []
    all_calls = []

    # Walk the repo folder
    for root, _, files in os.walk(REPO_FOLDER):
        for file in files:
            if not file.endswith(".java"):
                continue
            path = os.path.join(root, file)
            fragments = extract_classes_and_methods(path)
            all_fragments.extend(fragments)
            for frag in fragments:
                for callee in frag["calls"]:
                    all_calls.append({"caller": frag["symbol"], "callee": callee})

    # Generate embeddings and insert into Mongo
    for frag in tqdm(all_fragments):
        try:
            emb = get_embedding(frag["code"])
            frag["embedding"] = emb
            insert_fragment(frag)
        except Exception as e:
            print(f"Error processing {frag['symbol']}: {e}")

    # Insert method calls into Neo4j
    for call in tqdm(all_calls):
        try:
            insert_method_call(call["caller"], call["callee"])
        except Exception as e:
            print(f"Error inserting call {call}: {e}")

if __name__ == "__main__":
    main()
