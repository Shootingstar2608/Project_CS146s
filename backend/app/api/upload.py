from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.db_models import Document
from backend.app.models.schemas import UploadResponse
from backend.app.config import settings
from backend.app.workers import process_document_task
import os
import uuid
import shutil
from datetime import datetime, timezone

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. Basic Validation
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Create upload dir if not exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    document_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_{file.filename}")
    
    # 2. Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    # 3. Save metadata to DB
    new_doc = Document(
        id=document_id,
        filename=file.filename,
        original_path=file_path,
        status="processing",
        uploaded_at=datetime.now(timezone.utc)
    )
    
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    # 4. Trigger Celery task for processing
    process_document_task.delay(new_doc.id)
    
    return UploadResponse(
        document_id=new_doc.id,
        filename=new_doc.filename,
        status=new_doc.status,
        message="File uploaded successfully, processing started"
    )
