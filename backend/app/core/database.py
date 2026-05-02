"""
Core: Async Database Session Factory (PostgreSQL via SQLAlchemy).

Usage:
    async with get_db_session() as session:
        result = await session.execute(...)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _make_engine():
    from app.config import get_settings

    cfg = get_settings()
    return create_async_engine(
        cfg.postgres_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )


_engine = None
_session_factory = None


def _ensure_init():
    global _engine, _session_factory
    if _engine is None:
        _engine = _make_engine()
        _session_factory = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, auto-rolling-back on error."""
    _ensure_init()
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables (run once at startup)."""
    _ensure_init()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
