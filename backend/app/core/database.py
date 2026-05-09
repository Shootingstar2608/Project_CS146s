"""
Database: PostgreSQL async connection via SQLAlchemy.

- engine         : AsyncEngine (asyncpg driver)
- SessionLocal   : async_sessionmaker để tạo session trong endpoints
- init_db()      : tạo tất cả tables khi startup
- close_db()     : dispose engine khi shutdown
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


def _get_engine():
    """Lazy-create AsyncEngine (reads config at call time, not import time)."""
    from app.config import get_settings
    cfg = get_settings()
    return create_async_engine(
        cfg.postgres_url,
        pool_size=10,
        max_overflow=20,
        echo=False,
        future=True,
    )


# Lazy singletons — initialised on first use
_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# Convenience alias used by upload.py
SessionLocal = property(lambda self: get_session_factory())

# Make SessionLocal a callable at module level
class _SessionLocalProxy:
    def __call__(self):
        return get_session_factory()()

    def __aenter__(self):
        return get_session_factory().__aenter__()

    def __aexit__(self, *args):
        return get_session_factory().__aexit__(*args)


SessionLocal = _SessionLocalProxy()


async def get_db() -> AsyncSession:
    """FastAPI dependency: yield an async DB session."""
    async with get_session_factory()() as session:
        yield session


# Also expose engine for health check
@property
def engine():
    return get_engine()


async def init_db() -> None:
    """Create all tables defined in ORM models. Called at app startup."""
    from app.models.db_models import Base
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables created / verified")


async def close_db() -> None:
    """Dispose the engine connection pool. Called at app shutdown."""
    eng = get_engine()
    await eng.dispose()
    logger.info("PostgreSQL engine disposed")
