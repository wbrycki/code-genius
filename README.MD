# Code Genius Indexer

![Docker](https://img.shields.io/badge/docker-ready-blue)
![Python](https://img.shields.io/badge/python-3.11-brightgreen)

This project scans a codebase in a specified folder, generates embeddings for code fragments, stores them in **MongoDB**, and builds a **Neo4j graph** representing method calls. These embeddings and the graph can later be used to enhance code operations, including LLM-powered analysis.

---

## Features

- Extracts classes, methods, and method calls from Java code.
- Generates embeddings for code fragments using a transformer model.
- Stores embeddings in MongoDB.
- Builds a method-call graph in Neo4j.
- Fully containerized using Docker for easy setup.

---

## Setup & Usage

### 1. Add your code

Place all the code you want to scan in the folder:

```text
repo_to_index/
Each file inside this folder will be processed and converted into embeddings.
```

### 2. Start services with Docker

```bash
docker compose up --build
```

This will start:

- MongoDB
- Neo4j
- The code indexer

### 3. Inspect embeddings in MongoDB

Enter the MongoDB container:
```bash
docker exec -it mongo mongosh
```

Switch to the code_index database:
```bash
use code_index
```
View the embeddings:
```bash
db.code_memory.find().pretty()
```
Check the total number of fragments:
```bash
db.code_memory.countDocuments()
```

### 4. Neo4j Graph

- Neo4j runs on ports 7474 (HTTP) and 7687 (Bolt).

- Method-call relationships are stored in a graph for relational queries.

#### Configuration

- Embedding Model: Uses all-MiniLM-L6-v2 (lightweight, fast).
- Throttle Requests: EMBEDDING_BATCH_DELAY controls delay between embedding requests to reduce CPU/RAM usage.

You can change these in main.py if needed.

#### Notes

- Fully modular: you can replace the embedding model with any sentence-transformers compatible model.
- Ideal for LLM-powered code operations, analysis, or search.
