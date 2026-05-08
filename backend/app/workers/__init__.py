from celery import Celery
from backend.app.config import settings

celery_app = Celery(
    "graphrag_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["backend.app.workers"])

@celery_app.task(name="process_document_task")
def process_document_task(document_id: str):
    """
    Background task to process a document:
    1. Parse PDF
    2. Extract Entities & Relations
    3. Resolve Entities
    4. Load into Neo4j
    """
    # This is where we will call the pipeline functions
    print(f"Processing document: {document_id}")
    return {"status": "completed", "document_id": document_id}
