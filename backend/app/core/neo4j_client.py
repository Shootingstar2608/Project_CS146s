from neo4j import GraphDatabase
from backend.app.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jClient:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None

    @classmethod
    def execute_query(cls, query: str, parameters: dict = None):
        """
        Execute a Cypher query and return results as a list of dicts.
        """
        driver = cls.get_driver()
        with driver.session() as session:
            try:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
            except Exception as e:
                logger.error(f"Neo4j query error: {e}")
                raise e
