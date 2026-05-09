from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.models.db_models import Document

router = APIRouter(tags=["Documents"])

@router.get("/documents")
async def get_documents(db: AsyncSession = Depends(get_db)):
    """Lấy danh sách các file PDF đã upload từ Postgres."""
    result = await db.execute(
        select(Document).order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    
    # Lấy metadata từ Neo4j cho tất cả Paper nodes
    neo4j_metadata = {}
    try:
        from app.core.neo4j_client import Neo4jClient
        query = """
        MATCH (p:Paper)
        OPTIONAL MATCH (p)-[:AUTHORED_BY]->(a:Author)
        RETURN p.paper_id AS paper_id, p.name AS title, p.year AS year, p.categories AS categories, p.abstract AS abstract, collect(a.name) AS authors, p.keywords AS keywords
        """
        neo_results = Neo4jClient.execute_query(query)
        for r in neo_results:
            pid = str(r["paper_id"]) if r["paper_id"] else ""
            neo4j_metadata[pid] = {
                "title": r["title"] or "",
                "year": r["year"] or "",
                "categories": r["categories"] or ["Uncategorized"],
                "abstract": r["abstract"] or "",
                "authors": r["authors"] or [],
                "keywords": r["keywords"] or []
            }
    except Exception as e:
        print(f"Failed to fetch metadata from Neo4j: {e}")

    # Format lại để giống với interface Paper của frontend
    papers = []
    for doc in docs:
        meta = neo4j_metadata.get(doc.id, {})
        
        categories = meta.get("categories", ["Uncategorized"])
            
        papers.append({
            "id": doc.id,
            "title": meta.get("title") or doc.filename.replace(".pdf", ""),
            "fileName": doc.filename,
            "fileType": "application/pdf",
            "fileSize": 0,
            "categories": categories, 
            "status": "indexed" if (doc.status == "completed" or meta.get("title")) else "needs_review",
            "authors": meta.get("authors") or [],
            "year": meta.get("year") or "",
            "abstract": meta.get("abstract") or (doc.error_message if doc.status == "failed" else ""),
            "addedAt": doc.uploaded_at.isoformat() if doc.uploaded_at else "",
            "downloadUrl": f"/api/v1/files/{doc.id}/pdf",
        })
    return papers
