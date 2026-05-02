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


@celery_app.task(bind=True, name="ingest_pdf_task")
def ingest_pdf_task(self, file_path: str) -> dict:
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
        result = ingest_pdf(file_path)
        logger.info("[Celery] ingest_pdf_task done: %s", result)
        return result
    except Exception as exc:
        logger.error("[Celery] ingest_pdf_task failed: %s", exc)
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise