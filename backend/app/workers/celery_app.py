"""
Celery Application + Tasks.

Broker/backend: Redis
Tasks:
  - ingest_pdf_task  : full PDF ingestion pipeline (FAISS + Neo4j)
"""

from celery import Celery

celery_app = Celery(
    "graphrag",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
)


def _update_document_status_sync(paper_id: str, status: str) -> None:
    """Update document status using a local async DB connection from Celery."""
    import asyncio
    import logging

    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.models.db_models import Document

    logger = logging.getLogger(__name__)
    cfg = get_settings()

    async def _run_update() -> None:
        engine = create_async_engine(cfg.postgres_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with session_factory() as session:
                await session.execute(
                    update(Document)
                    .where(Document.id == paper_id)
                    .values(status=status)
                )
                await session.commit()
            logger.info("[Celery] Document %s status updated to %s", paper_id, status)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run_update())
    except Exception as exc:
        logger.error("[Celery] Failed to update status for %s: %s", paper_id, exc)


@celery_app.task(bind=True, name="ingest_pdf_task")
def ingest_pdf_task(self, file_path: str, paper_id: str = None) -> dict:
    """
    Celery task: run the full ingestion pipeline for one PDF.

    Steps (inside pipeline.embedding.ingest.ingest_pdf):
      1. PDF parse (PyMuPDF)
      2. LLM metadata extraction (title, authors, year)
      3. Section splitting + chunking
      4. Batch embedding (SentenceTransformers)
      5. FAISS index update + save
      6. KG entity/relation extraction + Neo4j write

    Args:
        file_path: Absolute path to the saved PDF file.

    Returns:
        Summary dict: {paper_id, title, num_chunks, num_pages, ...}
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[Celery] ingest_pdf_task started: %s", file_path)

    try:
        from pipeline.embedding.ingest import ingest_pdf
        result = ingest_pdf(file_path, paper_id=paper_id)
        logger.info("[Celery] ingest_pdf_task done: %s", result)
        
        # Update status to completed in DB
        if paper_id:
            _update_document_status_sync(paper_id, "completed")
            
        return result
    except Exception as exc:
        logger.error("[Celery] ingest_pdf_task failed: %s", exc, exc_info=True)
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        
        # Update status to failed in DB
        if paper_id:
            _update_document_status_sync(paper_id, "failed")
                
        raise