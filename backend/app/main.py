"""
FastAPI Application Entrypoint.

Lifecycle:
  startup  → init PostgreSQL tables, verify Neo4j connectivity
  shutdown → close all DB connections (PostgreSQL, Neo4j)

Routers:
  /api/v1/upload  — PDF upload + async ingestion trigger
  /api/v1/chat    — Hybrid GraphRAG Q&A
  /health         — Health check (for Docker / load balancer)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import upload, router_chat, router_documents, router_graph, router_files
from app.config import get_settings
from app.core.database import init_db, close_db
from app.core.neo4j_client import close_driver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup → yield → shutdown."""
    cfg = get_settings()

    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("=== GraphRAG Backend starting up ===")

    # 1. Initialise PostgreSQL (create tables if they don't exist)
    try:
        await init_db()
        logger.info("PostgreSQL: tables ready")
    except Exception as exc:
        logger.error("PostgreSQL init failed: %s", exc)

    # 2. Verify Neo4j connectivity (non-fatal on startup)
    try:
        from app.core.neo4j_client import Neo4jClient
        Neo4jClient.execute_query("RETURN 1 AS ok")
        logger.info("Neo4j: connection OK")
    except Exception as exc:
        logger.warning("Neo4j not reachable on startup (will retry on first query): %s", exc)

    # 3. Ensure upload directory exists
    import os
    os.makedirs(cfg.upload_dir, exist_ok=True)
    logger.info("Upload directory: %s", cfg.upload_dir)

    yield  # ← app is running here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("=== GraphRAG Backend shutting down ===")
    await close_db()
    close_driver()
    logger.info("All connections closed.")


# ── FastAPI app ───────────────────────────────────────────────────────────────

cfg = get_settings()

app = FastAPI(
    title="Autonomous Graph-RAG Agent",
    description=(
        "Backend API for the CS146 Graph-RAG research assistant.\n\n"
        "- **/api/v1/upload** — Upload academic PDFs for ingestion into the Knowledge Graph\n"
        "- **/api/v1/chat**   — Query the Hybrid GraphRAG agent (graph + vector retrieval)\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload.router,      prefix="/api/v1")
app.include_router(router_chat.router, prefix="/api/v1")
app.include_router(router_documents.router, prefix="/api/v1")
app.include_router(router_graph.router, prefix="/api/v1")
app.include_router(router_files.router, prefix="/api/v1")

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """
    Quick liveness probe — returns 200 if the backend process is alive.
    Does NOT check database connectivity (use /health/full for that).
    """
    return {"status": "ok", "service": "graphrag-backend"}


@app.get("/health/full", tags=["System"])
async def health_check_full() -> dict:
    """Deep health check: verifies PostgreSQL and Neo4j connectivity."""
    result: dict = {"status": "ok", "postgres": "unknown", "neo4j": "unknown"}

    # PostgreSQL
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        result["postgres"] = "ok"
    except Exception as exc:
        result["postgres"] = f"error: {exc}"
        result["status"] = "degraded"

    # Neo4j
    try:
        from app.core.neo4j_client import Neo4jClient
        Neo4jClient.execute_query("RETURN 1 AS ok")
        result["neo4j"] = "ok"
    except Exception as exc:
        result["neo4j"] = f"error: {exc}"
        result["status"] = "degraded"

    return result
