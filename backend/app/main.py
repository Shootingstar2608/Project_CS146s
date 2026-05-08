from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.app.config import settings
from backend.app.core.database import init_db, close_db
from backend.app.core.neo4j_client import Neo4jClient
from agent.graph import run_agent
from backend.app.api import upload
from backend.app.models.db_models import Document
from backend.app.models.schemas import ChatRequest, ChatResponse, DocumentListResponse, DocumentInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    await init_db()
    yield
    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    Neo4jClient.close()

app = FastAPI(
    title="Project CS146s - GraphRAG API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(upload.router, tags=["upload"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document))
    documents = result.scalars().all()
    return DocumentListResponse(
        documents=[
            DocumentInfo(
                id=doc.id,
                filename=doc.filename,
                status=doc.status,
                uploaded_at=doc.uploaded_at,
                entity_count=doc.entity_count,
                relation_count=doc.relation_count
            ) for doc in documents
        ],
        total=len(documents)
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = await run_agent(request.message)
        return ChatResponse(
            answer=result["answer"],
            reasoning_steps=result["reasoning_steps"],
            graph_data=result["graph_data"],
            sources=[] # TODO: implement sources
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Placeholder for other routes (upload, docs, etc.)
# from backend.app.api import upload
# app.include_router(upload.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
