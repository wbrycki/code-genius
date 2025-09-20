import os
import argparse
from tqdm import tqdm
from parser import extract_classes_and_methods
from mongo_utils import insert_fragment, is_file_unchanged, update_file_hash, calculate_file_hash
from neo4j_utils import insert_method_call, check_neo4j_connection, count_methods_and_calls
from sentence_transformers import SentenceTransformer

# -------- CONFIG --------
REPO_FOLDER = os.getenv("REPO_FOLDER", "/app/repo_to_index")
MODEL_NAME = "all-MiniLM-L6-v2"  # lightweight, fast embedding model

# -------- LOAD MODEL --------
print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)

def get_embedding(code_text):
    """Generate embedding vector using sentence-transformers."""
    return model.encode(code_text).tolist()

def main(full_rescan: bool = False):
    print(f"Indexing starting. REPO_FOLDER={REPO_FOLDER}")
    print(f"Mode: {'FULL RESCAN' if full_rescan else 'INCREMENTAL (MD5 cache)'}")

    all_fragments = []
    all_calls = []
    total_files = 0
    skipped_files = 0
    processed_files = 0

    # Walk the repo folder
    for root, _, files in os.walk(REPO_FOLDER):
        for file in files:
            # accept case-insensitive .java
            if not file.lower().endswith(".java"):
                continue
                
            path = os.path.join(root, file)
            total_files += 1
            
            # Skip unchanged files
            if not full_rescan and is_file_unchanged(path):
                skipped_files += 1
                print(f"Skipping unchanged file: {path}")
                continue
                
            print(f"Processing: {path}")
            fragments = extract_classes_and_methods(path)

            # Update hash for any processed file (even if no fragments were found)
            try:
                file_hash = calculate_file_hash(path)
                update_file_hash(path, file_hash)
            except Exception as e:
                print(f"Warning: failed to update hash for {path}: {e}")
            processed_files += 1
                
            all_fragments.extend(fragments)
            for frag in fragments:
                if frag.get("type") == "method":  # only method -> method edges
                    for callee in frag.get("calls", []):
                        all_calls.append({"caller": frag["symbol"], "callee": callee})

    # Generate embeddings and insert into Mongo
    for frag in tqdm(all_fragments):
        try:
            emb = get_embedding(frag["code"])
            frag["embedding"] = emb
            insert_fragment(frag)
        except Exception as e:
            print(f"Error processing {frag['symbol']}: {e}")

    # Insert method calls into Neo4j (optional)
    neo4j_enabled = os.getenv("NEO4J_ENABLED", "true").lower() not in {"0", "false", "no"}
    if not neo4j_enabled:
        print("Skipping Neo4j insertion (NEO4J_ENABLED=false)")
    else:
        if not check_neo4j_connection():
            print("Skipping Neo4j insertion (connection unavailable or authentication failed).")
        else:
            errors = 0
            for call in tqdm(all_calls, desc="Neo4j method calls"):
                try:
                    insert_method_call(call["caller"], call["callee"])
                except Exception as e:
                    errors += 1
                    print(f"Error inserting call {call}: {e}")
                    # If we get repeated auth/rate-limit errors, stop spamming
                    if errors >= 5:
                        print("Too many Neo4j errors; stopping further inserts. Check NEO4J_* credentials and server status.")
                        break

    print("\nIndexing summary:")
    print(f"  Files discovered (.java): {total_files}")
    if total_files == 0:
        print("  Hint: Put your Java files under the folder above or set REPO_FOLDER to the correct path.")
    if not full_rescan:
        print(f"  Skipped (unchanged):      {skipped_files}")
    print(f"  Processed:                {processed_files}")

    # Neo4j graph summary (if enabled and reachable)
    if neo4j_enabled and check_neo4j_connection():
        n, r = count_methods_and_calls()
        if n is not None:
            print(f"  Neo4j Methods nodes:      {n}")
            print(f"  Neo4j CALLS relationships:{r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code Genius Indexer")
    parser.add_argument("--full-rescan", action="store_true", help="Re-scan all files regardless of MD5 cache")
    args = parser.parse_args()

    main(full_rescan=args.full_rescan)
