"""
API Router: File Download & PDF Serving

Serves uploaded PDF files with proper MIME type and download headers.
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.core.database import get_session_factory
from app.models.db_models import Document

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/{doc_id}/pdf")
async def get_pdf_file(doc_id: str):
    """
    Serve the PDF file for a given document ID.
    
    Returns: PDF file with Content-Disposition: attachment (download).
    """
    cfg = get_settings()
    upload_dir = Path(cfg.upload_dir)
    
    # 1. Look up document in PostgreSQL to get the filename
    async with get_session_factory()() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        filename = doc.filename
        original_path = doc.original_path
    
    # 2. Construct file path
    if original_path:
        file_path = Path(original_path)
    else:
        file_path = upload_dir / filename
    
    # 3. Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"PDF file not found at {file_path}"
        )
    
    # 4. Serve file with download header
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{doc_id}")
async def get_file_info(doc_id: str):
    """
    Return file metadata (for frontend to know download URL).
    """
    async with get_session_factory()() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        return {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "download_url": f"/api/v1/files/{doc.id}/pdf",
        }
