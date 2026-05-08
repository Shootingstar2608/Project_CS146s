from ast import List
from typing import Annotated
from fastapi import APIRouter, HTTPException, UploadFile, Depends, File
from starlette.status import HTTP_201_CREATED
from models import UploadResponse
from models import Document
from sqlalchemy.ext.asyncio import AsyncSession
from core import get_db
from pathlib import Path
import magic
import logging
import uuid
import aiofiles

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_MIME_TYPE = ["application/pdf"]


# validate if valid pdf using magic library
async def validate_file(file: UploadFile):
    header = await file.read(2048)
    await file.seek(0)
    mime = await magic.from_buffer(header, mime=True)

    if mime not in ALLOWED_MIME_TYPE:
        logger.exception("File type not supported")
        raise HTTPException(400, "Only .pdf files are accepted.")

    return mime


@router.post("/", response_model=List[UploadResponse], status_code=HTTP_201_CREATED)
async def upload(
    files: Annotated(List[UploadFile], File(...)), db: AsyncSession = Depends(get_db)
):
    response = []
    total_files = len(files)
    file_saved = 0

    for file in files:
        await validate_file(file)

        doc_id = str(uuid.uuid4())
        doc_name = file.name
        file_path = f"{UPLOAD_DIR}/{doc_name}"

        # dealing with server's disk file
        async with aiofiles.open(file_path, mode="wb") as out_file:
            while content := await file.read(1024 * 1024):
                out_file.write(content)

        new_doc = Document(
            id=doc_id, status="processing", filename=file.name, original_path=file_path
        )
        file_response = UploadResponse(
            document_id=doc_id,
            filename=file.name,
            status="processing",
        )

        try:
            await db.add(new_doc)
            file_saved += 1
            logger.info(f"Saved {file.name}, process: {file.saved}/{total_files}")
            response.append(file_response)
        except Exception as e:
            logger.exception(f"{e}: Failed to save file")

    return response
