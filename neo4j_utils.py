from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def insert_method_call(caller, callee):
    with driver.session() as session:
        session.run(
            """
            MERGE (c:Method {name:$caller})
            MERGE (d:Method {name:$callee})
            MERGE (c)-[:CALLS]->(d)
            """,
            caller=caller,
            callee=callee
        )
