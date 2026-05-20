import os
import argparse
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

from parser import extract_classes_and_methods

from qdrant_utils import (
    init_collections,
    batch_insert_fragments,
    is_file_unchanged,
    update_file_hash,
    calculate_file_hash,
)

from neo4j_utils import (
    insert_method_call,
    check_neo4j_connection,
    count_methods_and_calls,
)

# -----------------------------------
# CONFIG
# -----------------------------------

REPO_FOLDER = os.getenv("REPO_FOLDER", "/app/repo_to_index")

MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "all-MiniLM-L6-v2"
)

BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

EMBEDDING_INSERT_CHUNK_SIZE = int(
    os.getenv("EMBEDDING_INSERT_CHUNK_SIZE", "512")
)

MIN_CODE_CHARS = int(os.getenv("MIN_CODE_CHARS", "80"))

EMBED_METHODS_ONLY = (
    os.getenv("EMBED_METHODS_ONLY", "true").lower()
    not in {"0", "false", "no"}
)

# -----------------------------------
# LOAD MODEL
# -----------------------------------

print(f"Loading embedding model: {MODEL_NAME}")

model = SentenceTransformer(MODEL_NAME)

# -----------------------------------
# HELPERS
# -----------------------------------

def should_embed_fragment(fragment: dict) -> bool:
    """
    Decide whether a fragment should be embedded.
    """

    if EMBED_METHODS_ONLY and fragment.get("type") != "method":
        return False

    code = fragment.get("code", "")

    if not code:
        return False

    if len(code.strip()) < MIN_CODE_CHARS:
        return False

    return True


def batch_insert_embeddings(fragments: list[dict]):
    """
    Generate embeddings in batches and insert into Qdrant.
    """

    if not fragments:
        return

    inserted = 0

    for start in range(0, len(fragments), EMBEDDING_INSERT_CHUNK_SIZE):
        chunk = fragments[start:start + EMBEDDING_INSERT_CHUNK_SIZE]
        codes = [f["code"] for f in chunk]

        embeddings = model.encode(
            codes,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
        )

        for frag, emb in zip(chunk, embeddings):

            try:
                frag["embedding"] = emb.tolist()

            except Exception as e:
                print(f"Error processing fragment {frag.get('symbol')}: {e}")

        batch_insert_fragments(chunk)
        inserted += len(chunk)
        print(f"Inserted embeddings into Qdrant: {inserted}/{len(fragments)}")


# -----------------------------------
# MAIN
# -----------------------------------

def main(full_rescan: bool = False):

    # Initialize Qdrant collections
    init_collections()

    print(f"Indexing starting. REPO_FOLDER={REPO_FOLDER}")

    print(
        f"Mode: {'FULL RESCAN' if full_rescan else 'INCREMENTAL (MD5 cache)'}"
    )

    total_files = 0
    skipped_files = 0
    processed_files = 0

    fragments_to_embed = []

    # deduplicate graph edges
    all_calls = set()

    # -----------------------------------
    # WALK REPOSITORY
    # -----------------------------------

    for root, _, files in os.walk(REPO_FOLDER):

        for file in files:

            if not file.lower().endswith(".java"):
                continue

            path = os.path.join(root, file)

            total_files += 1

            # -----------------------------------
            # SKIP UNCHANGED FILES
            # -----------------------------------

            if not full_rescan and is_file_unchanged(path):

                skipped_files += 1

                print(f"Skipping unchanged file: {path}")

                continue

            print(f"Processing: {path}")

            # -----------------------------------
            # PARSE FILE
            # -----------------------------------

            try:
                fragments = extract_classes_and_methods(path)

            except Exception as e:
                print(f"Failed parsing {path}: {e}")
                continue

            processed_files += 1

            # -----------------------------------
            # UPDATE FILE HASH
            # -----------------------------------

            try:
                file_hash = calculate_file_hash(path)
                update_file_hash(path, file_hash)

            except Exception as e:
                print(f"Warning: failed updating hash for {path}: {e}")

            # -----------------------------------
            # PROCESS FRAGMENTS
            # -----------------------------------

            for frag in fragments:

                # collect graph relationships
                if frag.get("type") == "method":

                    caller = frag.get("symbol")

                    for callee in frag.get("calls", []):

                        all_calls.add((caller, callee))

                # collect embeddable fragments
                if should_embed_fragment(frag):

                    fragments_to_embed.append(frag)

    # -----------------------------------
    # EMBEDDINGS
    # -----------------------------------

    print(
        f"\nGenerating embeddings for "
        f"{len(fragments_to_embed)} fragments..."
    )

    batch_insert_embeddings(fragments_to_embed)

    # -----------------------------------
    # NEO4J
    # -----------------------------------

    neo4j_enabled = (
        os.getenv("NEO4J_ENABLED", "true").lower()
        not in {"0", "false", "no"}
    )

    if not neo4j_enabled:

        print("Skipping Neo4j insertion (disabled).")

    else:

        if not check_neo4j_connection():

            print(
                "Skipping Neo4j insertion "
                "(connection unavailable)."
            )

        else:

            print(
                f"\nInserting {len(all_calls)} "
                f"method-call relationships into Neo4j..."
            )

            errors = 0

            for caller, callee in tqdm(
                all_calls,
                desc="Neo4j method calls"
            ):

                try:

                    insert_method_call(caller, callee)

                except Exception as e:

                    errors += 1

                    print(
                        f"Error inserting relationship "
                        f"{caller} -> {callee}: {e}"
                    )

                    if errors >= 5:

                        print(
                            "Too many Neo4j errors. "
                            "Stopping insertion."
                        )

                        break

    # -----------------------------------
    # SUMMARY
    # -----------------------------------

    print("\n=== INDEXING SUMMARY ===")

    print(f"Files discovered (.java): {total_files}")

    if total_files == 0:

        print(
            "Hint: Put Java files under REPO_FOLDER "
            "or update the path."
        )

    if not full_rescan:

        print(f"Skipped unchanged:       {skipped_files}")

    print(f"Processed files:         {processed_files}")

    print(f"Embedded fragments:      {len(fragments_to_embed)}")

    print(f"Unique graph edges:      {len(all_calls)}")

    # -----------------------------------
    # GRAPH SUMMARY
    # -----------------------------------

    if neo4j_enabled and check_neo4j_connection():

        n, r = count_methods_and_calls()

        if n is not None:

            print(f"Neo4j method nodes:     {n}")

            print(f"Neo4j CALLS edges:      {r}")


# -----------------------------------
# ENTRYPOINT
# -----------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Code Genius Indexer"
    )

    parser.add_argument(
        "--full-rescan",
        action="store_true",
        help="Re-index all files regardless of MD5 cache",
    )

    args = parser.parse_args()

    main(full_rescan=args.full_rescan)
