"""
API Router: Upload PDF

Flow:
  1. Validate file (type, size)
  2. Save to disk (UPLOAD_DIR)
  3. Create Document record in PostgreSQL (status=processing)
  4. Dispatch Celery task ingest_pdf_task (async ingestion)
     → Fallback: run ingest_pdf() inline if Celery/Redis unavailable
  5. Return 201 UploadResponse immediately (don't wait for ingestion)
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from starlette.status import HTTP_201_CREATED

from app.config import get_settings
from app.core.database import get_session_factory
from app.models.db_models import Document
from app.models.schemas import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

# Allowed MIME types
ALLOWED_MIME = {"application/pdf"}
ALLOWED_EXT = {".pdf"}


@router.post(
    "/",
    response_model=UploadResponse,
    status_code=HTTP_201_CREATED,
    summary="Upload a PDF paper for ingestion into the Knowledge Graph",
)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    """
    Accept a single PDF file, save it to disk, and trigger async ingestion.

    Returns immediately with status='processing'. The actual ingestion
    (embedding + Neo4j KG write) runs in a Celery background worker.
    """
    cfg = get_settings()

    # ── Validate file type ────────────────────────────────────────────────────
    ext = Path(file.filename or "").suffix.lower()
    content_type = file.content_type or ""

    if ext not in ALLOWED_EXT or content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid file type '{content_type}' (ext: '{ext}'). "
                "Only PDF files are accepted."
            ),
        )

    # ── Validate file size ────────────────────────────────────────────────────
    max_bytes = cfg.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large ({len(content) / 1024 / 1024:.1f} MB). "
                f"Maximum allowed: {cfg.max_upload_size_mb} MB."
            ),
        )

    # ── Persist to disk ───────────────────────────────────────────────────────
    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}_{Path(file.filename or 'upload').name}"
    upload_dir = Path(cfg.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / safe_filename

    try:
        file_path.write_bytes(content)
        logger.info("File saved: %s (%d bytes)", file_path, len(content))
    except OSError as exc:
        logger.error("Failed to save file: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    # ── Create Document record in PostgreSQL ──────────────────────────────────
    async with get_session_factory()() as db:
        doc = Document(
            id=doc_id,
            filename=file.filename or safe_filename,
            original_path=str(file_path),
            status="processing",
        )
        db.add(doc)
        try:
            await db.commit()
            logger.info("Document record created: id=%s", doc_id)
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.error("DB commit failed: %s", exc)
            raise HTTPException(status_code=500, detail="Database error while saving document.")

    # ── Dispatch Celery task ──────────────────────────────────────────────────
    task_dispatched = False
    try:
        from app.workers.celery_app import ingest_pdf_task
        ingest_pdf_task.delay(str(file_path), paper_id=doc_id)
        task_dispatched = True
        logger.info("Celery task dispatched for: %s", file_path)
    except Exception as exc:
        logger.warning(
            "Celery unavailable (%s) — falling back to inline ingestion.", exc
        )

    # ── Fallback: inline (sync) ingestion ─────────────────────────────────────
    if not task_dispatched:
        try:
            from pipeline.embedding.ingest import ingest_pdf
            result = ingest_pdf(str(file_path), paper_id=doc_id)
            # Update document status to completed
            async with get_session_factory()() as db:
                doc_obj = await db.get(Document, doc_id)
                if doc_obj:
                    doc_obj.status = "completed"
                    doc_obj.entity_count = result.get("entity_count", 0)
                    doc_obj.relation_count = result.get("relation_count", 0)
                    await db.commit()
            logger.info("Inline ingestion completed for: %s", file_path)
        except Exception as exc:
            logger.error("Inline ingestion failed: %s", exc)
            # Don't raise — return processing status; user can check later

    return UploadResponse(
        document_id=doc_id,
        filename=file.filename or safe_filename,
        status="processing",
        message=(
            "File received and queued for ingestion via Celery."
            if task_dispatched
            else "File received. Ingestion completed inline (Celery unavailable)."
        ),
    )
