FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy indexer code (main.py, parser.py, mongo_utils.py, neo4j_utils.py)
COPY main.py parser.py mongo_utils.py neo4j_utils.py ./

# Mount repo folder for live code scanning
# This comes from docker-compose volumes

CMD ["python", "main.py"]
