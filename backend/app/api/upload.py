from ast import List
from fastapi import APIRouter, UploadFile, Depends
from starlette.status import HTTP_201_CREATED
from backend.app.models.schemas import UploadResponse
from models import Document
from sqlalchemy.ext.asyncio import AsyncSession
from core import get_db

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/", response_model=UploadResponse, status_code=HTTP_201_CREATED)
def upload(files: List[UploadFile], db: AsyncSession = Depends(get_db)):
    for f in files:
        pass
