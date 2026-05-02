"""
FastAPI Application — Entry Point.

Endpoints:
  GET  /api/health           — liveness probe
  POST /api/upload           — PDF ingest (Celery task)
  POST /api/query            — Hybrid KG + vector search → LLM answer
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown tasks."""
    from app.config import get_settings
    from app.core.database import create_all_tables

    cfg = get_settings()
    Path(cfg.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.vector_store_path).mkdir(parents=True, exist_ok=True)

    # Import db_models so their tables are registered with Base.metadata
    import app.models.db_models  # noqa: F401

    await create_all_tables()
    logger.info("GraphRAG backend started ✓")

    yield

    from app.core.neo4j_client import Neo4jClient
    Neo4jClient.close()
    logger.info("GraphRAG backend stopped.")


# ── App ───────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    from app.config import get_settings
    cfg = get_settings()

    app = FastAPI(
        title="Graph-RAG Hybrid Search API",
        description=(
            "Academic paper QA using Knowledge Graph (Neo4j) + "
            "Vector Embeddings (FAISS) hybrid retrieval."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float | None = None  # override hybrid weight (0=KG, 1=vector)


class QueryResponse(BaseModel):
    answer: str
    reasoning_steps: list[str]
    retrieved_chunks: list[dict]
    graph_data: dict
    retrieval_mode: str
    alpha_used: float


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "graphrag-hybrid"}


@app.post("/api/upload", tags=["Ingestion"])
async def upload_pdf(file: UploadFile = File(...)):
    """
    Accept a PDF and trigger async ingestion:
    PDF parse → KG extraction → embedding pipeline.
    """
    from app.config import get_settings
    cfg = get_settings()

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    max_bytes = cfg.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {cfg.max_upload_size_mb} MB",
        )

    save_path = Path(cfg.upload_dir) / file.filename
    save_path.write_bytes(content)

    # Fire-and-forget via Celery
    try:
        from app.workers.celery_app import ingest_pdf_task
        task = ingest_pdf_task.delay(str(save_path))
        return {"status": "queued", "task_id": task.id, "filename": file.filename}
    except Exception as exc:
        logger.warning("Celery unavailable, running inline: %s", exc)
        # Fallback: inline (blocking) for dev
        from pipeline.embedding.ingest import ingest_pdf
        result = ingest_pdf(str(save_path))
        return {"status": "completed_inline", "filename": file.filename, **result}


@app.post("/api/query", response_model=QueryResponse, tags=["Query"])
async def hybrid_query(req: QueryRequest):
    """
    Run the full hybrid retrieval pipeline and return a grounded answer.
    """
    from agent.graph import run_agent

    result = await run_agent(req.query, alpha_override=req.alpha, top_k=req.top_k)

    return QueryResponse(
        answer=result.get("answer", ""),
        reasoning_steps=result.get("reasoning_steps", []),
        retrieved_chunks=result.get("retrieved_chunks", []),
        graph_data=result.get("graph_data", {}),
        retrieval_mode=result.get("retrieval_mode", "hybrid"),
        alpha_used=result.get("alpha_used", 0.5),
    )
