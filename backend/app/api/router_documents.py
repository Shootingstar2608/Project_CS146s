import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.db_models import Document

logger = logging.getLogger(__name__)

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
        OPTIONAL MATCH (p)<-[:AUTHORED]-(a:Author)
        OPTIONAL MATCH (p)-[:AUTHORED_BY]->(legacy:Author)
        RETURN p.paper_id AS paper_id,
               p.name AS title,
               p.year AS year,
               p.categories AS categories,
               p.abstract AS abstract,
               collect(DISTINCT a.name) + collect(DISTINCT legacy.name) AS authors,
               p.keywords AS keywords
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


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Xoá 1 document khỏi toàn bộ hệ thống (cascade):
      - Postgres : xoá record Document
      - Disk     : xoá file PDF gốc
      - Neo4j    : DETACH DELETE node Paper (chỉ Paper, giữ lại entity dùng chung)
      - FAISS    : xoá các chunk vector thuộc paper này

    Trả về:
      204 No Content  — xoá sạch, mọi store đều bị tác động.
      200 JSON        — có bước no-op hoặc lỗi mềm (kèm summary để client kiểm tra).
      404             — không tìm thấy Document trong Postgres.
    """
    # 1. Tải Document trước (cần original_path + để guard 404).
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    original_path: str | None = doc.original_path
    summary: dict[str, Any] = {
        "document_id": doc_id,
        "postgres": {"deleted": False},
        "disk": {"deleted": False, "no_op": False, "path": original_path},
        "neo4j": {"deleted_count": 0, "no_op": False},
        "faiss": {"deleted_count": 0, "no_op": False},
        "errors": [],
        "no_ops": [],
    }

    # 2. Disk: xoá file PDF đã upload.
    if original_path:
        try:
            Path(original_path).unlink()
            summary["disk"]["deleted"] = True
        except FileNotFoundError:
            summary["disk"]["no_op"] = True
            summary["no_ops"].append("disk:file_missing")
        except OSError as exc:
            logger.exception("disk unlink failed for document %s", doc_id)
            summary["errors"].append({"step": "disk", "error": str(exc)})
    else:
        summary["disk"]["no_op"] = True
        summary["no_ops"].append("disk:empty_original_path")

    # 3. Neo4j: DETACH DELETE node Paper (an toàn — không đụng entity dùng chung).
    try:
        from app.core.neo4j_client import Neo4jClient

        cypher = """
        OPTIONAL MATCH (p:Paper {paper_id: $paper_id})
        WITH collect(p) AS papers
        FOREACH (p IN papers | DETACH DELETE p)
        RETURN size(papers) AS deleted_count
        """
        rows = Neo4jClient.execute_write(cypher, {"paper_id": doc_id})
        n4j_count = int(rows[0]["deleted_count"]) if rows else 0
        summary["neo4j"]["deleted_count"] = n4j_count
        if n4j_count == 0:
            summary["neo4j"]["no_op"] = True
            summary["no_ops"].append("neo4j:paper_missing")
    except Exception as exc:
        logger.exception("Neo4j delete failed for document %s", doc_id)
        summary["errors"].append({"step": "neo4j", "error": str(exc)})

    # 4. FAISS: rebuild index không còn chunk của paper này (serialise qua lock).
    try:
        from pipeline.embedding.vector_store import get_vector_store, vector_store_lock

        with vector_store_lock:
            store = get_vector_store()
            faiss_count = store.delete_by_paper_id(doc_id)
            if faiss_count > 0:
                store.save()
        summary["faiss"]["deleted_count"] = faiss_count
        if faiss_count == 0:
            summary["faiss"]["no_op"] = True
            summary["no_ops"].append("faiss:chunks_missing")
    except Exception as exc:
        logger.exception("FAISS delete failed for document %s", doc_id)
        summary["errors"].append({"step": "faiss", "error": str(exc)})

    # 5. Postgres: xoá record sau cùng (đã đọc original_path ở trên).
    try:
        await db.delete(doc)
        await db.commit()
        summary["postgres"]["deleted"] = True
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("Postgres delete failed for document %s", doc_id)
        summary["errors"].append({"step": "postgres", "error": str(exc)})

    if not summary["errors"] and not summary["no_ops"]:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return JSONResponse(status_code=status.HTTP_200_OK, content=summary)
