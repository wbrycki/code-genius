from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test")

_driver = None

def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver

def check_neo4j_connection() -> bool:
    """Return True if we can run a trivial query; False otherwise."""
    try:
        drv = _get_driver()
        with drv.session() as session:
            session.run("RETURN 1 AS ok").consume()
        return True
    except Neo4jError as e:
        # Authentication issues or rate limit will land here
        print(f"Neo4j unavailable: {e}")
        return False
    except Exception as e:
        print(f"Neo4j connection error: {e}")
        return False

def insert_method_call(caller, callee):
    drv = _get_driver()
    with drv.session() as session:
        session.run(
            """
            MERGE (c:Method {name:$caller})
            MERGE (d:Method {name:$callee})
            MERGE (c)-[:CALLS]->(d)
            """,
            caller=caller,
            callee=callee
        )

def count_methods_and_calls():
    """Return a tuple (#methods, #CALLS relationships)."""
    drv = _get_driver()
    with drv.session() as session:
        try:
            n = session.run("MATCH (n:Method) RETURN count(n) AS c").single()["c"]
            r = session.run("MATCH ()-[r:CALLS]->() RETURN count(r) AS c").single()["c"]
            return int(n), int(r)
        except Exception as e:
            print(f"Failed to count Neo4j nodes/relationships: {e}")
            return None, None

def get_callees(method_name: str, limit: int = 10):
    """Return a list of method names that are called by the given method."""
    drv = _get_driver()
    with drv.session() as session:
        q = (
            "MATCH (m:Method {name:$name})-[:CALLS]->(t:Method) "
            "RETURN t.name AS name LIMIT $limit"
        )
        return [rec["name"] for rec in session.run(q, name=method_name, limit=limit)]

def get_callers(method_name: str, limit: int = 10):
    """Return a list of method names that call the given method."""
    drv = _get_driver()
    with drv.session() as session:
        q = (
            "MATCH (s:Method)-[:CALLS]->(m:Method {name:$name}) "
            "RETURN s.name AS name LIMIT $limit"
        )
        return [rec["name"] for rec in session.run(q, name=method_name, limit=limit)]
