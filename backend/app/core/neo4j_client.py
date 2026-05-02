"""
Core: Neo4j Client — connection pool + typed query execution.

Usage:
    records = Neo4jClient.execute_query("MATCH (p:Paper) RETURN p LIMIT 5")
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List

from neo4j import GraphDatabase, ManagedTransaction, Session
from neo4j.exceptions import Neo4jError, ServiceUnavailable

logger = logging.getLogger(__name__)


class _Neo4jClientSingleton:
    """Lazy-initialised Neo4j driver singleton."""

    def __init__(self) -> None:
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            from app.config import get_settings

            cfg = get_settings()
            self._driver = GraphDatabase.driver(
                cfg.neo4j_uri,
                auth=(cfg.neo4j_user, cfg.neo4j_password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
            logger.info("Neo4j driver initialised at %s", cfg.neo4j_uri)
        return self._driver

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        driver = self._get_driver()
        with driver.session() as session:
            yield session

    def execute_query(
        self,
        cypher: str,
        params: Dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Run a read Cypher query and return results as list-of-dicts.

        Args:
            cypher: Cypher query string.
            params: Optional parameters dict.
            timeout: Per-query timeout in seconds.

        Returns:
            List of records as plain dicts.

        Raises:
            Neo4jError: On query-level errors.
            ServiceUnavailable: When the database cannot be reached.
        """
        params = params or {}

        def _run(tx: ManagedTransaction) -> List[Dict[str, Any]]:
            result = tx.run(cypher, **params)
            return [record.data() for record in result]

        try:
            with self.session() as session:
                return session.execute_read(_run, timeout=timeout)
        except ServiceUnavailable as exc:
            logger.error("Neo4j unavailable: %s", exc)
            raise
        except Neo4jError as exc:
            logger.error("Cypher error [%s]: %s\nQuery: %s", exc.code, exc.message, cypher)
            raise

    def execute_write(
        self,
        cypher: str,
        params: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Run a write Cypher query (MERGE / CREATE / SET)."""
        params = params or {}

        def _run(tx: ManagedTransaction) -> List[Dict[str, Any]]:
            result = tx.run(cypher, **params)
            return [record.data() for record in result]

        with self.session() as session:
            return session.execute_write(_run)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")


# Module-level singleton
Neo4jClient = _Neo4jClientSingleton()
