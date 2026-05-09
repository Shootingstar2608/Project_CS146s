"""
Neo4j Client — Singleton driver cho toàn bộ backend và pipeline.

Cung cấp:
  - get_driver()        : sync Driver (dùng trong pipeline background tasks)
  - get_async_driver()  : async AsyncDriver (dùng trong FastAPI async endpoints)
  - Neo4jClient         : Singleton object với execute_query() / execute_write()
                          (được dùng bởi retriever.py và ingest.py)
  - close_driver()      : đóng cả hai drivers khi app shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, List

from neo4j import AsyncDriver, AsyncGraphDatabase, Driver, GraphDatabase, ManagedTransaction, Session
from neo4j.exceptions import Neo4jError, ServiceUnavailable

logger = logging.getLogger(__name__)


# ── Module-level driver singletons ────────────────────────────────────────────

_sync_driver: Driver | None = None
_async_driver: AsyncDriver | None = None


def _neo4j_credentials() -> tuple[str, str, str]:
    """Read Neo4j connection params from config (with env-var fallback)."""
    try:
        from app.config import get_settings
        cfg = get_settings()
        return cfg.neo4j_uri, cfg.neo4j_user, cfg.neo4j_password
    except Exception:
        # Fallback to raw env vars (used by pipeline workers running outside FastAPI)
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "graphrag_secret_2024")
        return uri, user, password


def get_driver() -> Driver:
    """Return a cached sync Neo4j driver (thread-safe singleton)."""
    global _sync_driver
    if _sync_driver is None:
        uri, user, password = _neo4j_credentials()
        _sync_driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
        )
        logger.info("Neo4j sync driver initialised at %s", uri)
    return _sync_driver


async def get_async_driver() -> AsyncDriver:
    """Return a cached async Neo4j driver (for FastAPI async endpoints)."""
    global _async_driver
    if _async_driver is None:
        uri, user, password = _neo4j_credentials()
        _async_driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
        )
        logger.info("Neo4j async driver initialised at %s", uri)
    return _async_driver


def close_driver() -> None:
    """Close both drivers. Call on application shutdown."""
    global _sync_driver, _async_driver
    if _sync_driver is not None:
        _sync_driver.close()
        _sync_driver = None
        logger.info("Neo4j sync driver closed")
    if _async_driver is not None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_async_driver.close())
            else:
                loop.run_until_complete(_async_driver.close())
        except Exception as exc:
            logger.warning("Error closing async Neo4j driver: %s", exc)
        finally:
            _async_driver = None
            logger.info("Neo4j async driver closed")


# ── Singleton helper class (used by retriever.py and ingest.py) ───────────────

class _Neo4jClientSingleton:
    """
    Thin wrapper around the sync driver providing typed execute helpers.

    Usage:
        from app.core.neo4j_client import Neo4jClient

        records = Neo4jClient.execute_query("MATCH (p:Paper) RETURN p LIMIT 5")
        Neo4jClient.execute_write("MERGE (n:Paper {name: $name})", {"name": "BERT"})
    """

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        driver = get_driver()
        with driver.session() as s:
            yield s

    def execute_query(
        self,
        cypher: str,
        params: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Run a READ Cypher query and return results as list of plain dicts.

        Raises:
            Neo4jError: On Cypher-level errors.
            ServiceUnavailable: When Neo4j cannot be reached.
        """
        params = params or {}

        def _run(tx: ManagedTransaction) -> List[Dict[str, Any]]:
            result = tx.run(cypher, **params)
            return [record.data() for record in result]

        try:
            with self.session() as s:
                return s.execute_read(_run)
        except ServiceUnavailable as exc:
            logger.error("Neo4j unavailable: %s", exc)
            raise
        except Neo4jError as exc:
            logger.error(
                "Cypher error [%s]: %s\nQuery: %s",
                exc.code,
                getattr(exc, "message", str(exc)),
                cypher,
            )
            raise

    def execute_write(
        self,
        cypher: str,
        params: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Run a WRITE Cypher query (MERGE / CREATE / SET).

        Raises:
            Neo4jError: On Cypher-level errors.
            ServiceUnavailable: When Neo4j cannot be reached.
        """
        params = params or {}

        def _run(tx: ManagedTransaction) -> List[Dict[str, Any]]:
            result = tx.run(cypher, **params)
            return [record.data() for record in result]

        try:
            with self.session() as s:
                return s.execute_write(_run)
        except ServiceUnavailable as exc:
            logger.error("Neo4j unavailable: %s", exc)
            raise
        except Neo4jError as exc:
            logger.error(
                "Cypher write error [%s]: %s\nQuery: %s",
                exc.code,
                getattr(exc, "message", str(exc)),
                cypher,
            )
            raise


# Module-level singleton — import this object directly
Neo4jClient = _Neo4jClientSingleton()
