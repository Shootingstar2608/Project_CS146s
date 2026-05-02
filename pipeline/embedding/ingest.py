"""
Embedding Pipeline: Ingest Orchestrator

End-to-end pipeline:
    PDF file
      → PyMuPDF parse (pdf_parser)
      → LLM metadata extraction (title, authors, year)
      → Section splitting
      → Text chunking (overlapping, 512 chars / 64 overlap)
      → Batch embedding (SentenceTransformers)
      → FAISS index update + save
      → KG entity/relation extraction + Neo4j MERGE

Called by:
  - Celery worker  (app/workers/celery_app.py :: ingest_pdf_task)
  - FastAPI inline fallback (/api/upload when Celery unavailable)
  - CLI / tests directly
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def ingest_pdf(
    file_path: str,
    paper_id: str | None = None,
    save_index: bool = True,
) -> dict:
    """
    Full ingestion pipeline for a single PDF file.

    Args:
        file_path:  Absolute path to the PDF.
        paper_id:   Stable identifier (defaults to filename stem).
        save_index: Whether to persist the FAISS index to disk after ingestion.

    Returns:
        Summary dict: {paper_id, title, num_chunks, num_pages, ...}
    """
    from pipeline.ingestion.pdf_parser import parse_pdf, split_into_sections
    from pipeline.extraction.entity_extractor import extract_paper_metadata
    from pipeline.embedding.chunker import chunk_section
    from pipeline.embedding.embedder import get_embedder
    from pipeline.embedding.vector_store import get_vector_store
    from app.config import get_settings

    cfg = get_settings()
    file_path = str(file_path)
    paper_id = paper_id or Path(file_path).stem

    logger.info("[ingest] Starting: %s (paper_id=%s)", file_path, paper_id)

    # ── Step 1: Parse PDF ─────────────────────────────────────────────────────
    parsed = parse_pdf(file_path)
    full_text: str = parsed["full_text"]
    num_pages: int = parsed["num_pages"]
    logger.info("[ingest] Parsed %d pages", num_pages)

    # ── Step 2: Extract paper metadata via LLM ────────────────────────────────
    meta = _safe_extract_metadata(full_text)
    title = meta.get("title", paper_id)
    authors = meta.get("authors", [])
    year = meta.get("year")
    keywords = meta.get("keywords", [])
    abstract = meta.get("abstract", "")
    logger.info("[ingest] Metadata: title=%r  authors=%s  year=%s", title, authors, year)

    # ── Step 3: Split into sections ───────────────────────────────────────────
    sections = split_into_sections(full_text)
    logger.info("[ingest] %d sections detected", len(sections))

    # ── Step 4: Chunk each section ────────────────────────────────────────────
    all_chunks = []
    global_offset = 0
    for sec in sections:
        chunks = chunk_section(
            section_heading=sec["heading"],
            section_text=sec["content"],
            paper_id=paper_id,
            paper_title=title,
            authors=authors,
            year=year,
            global_chunk_offset=global_offset,
            chunk_size=cfg.chunk_size,
            overlap=cfg.chunk_overlap,
        )
        all_chunks.extend(chunks)
        global_offset += len(chunks)

    logger.info("[ingest] Total chunks: %d", len(all_chunks))

    if not all_chunks:
        logger.warning("[ingest] No chunks produced for %s — skipping embedding", file_path)
        return {
            "paper_id": paper_id,
            "title": title,
            "num_chunks": 0,
            "num_pages": num_pages,
            "authors": authors,
            "year": year,
        }

    # ── Step 5: Embed ─────────────────────────────────────────────────────────
    embedder = get_embedder()
    texts = [c.text for c in all_chunks]
    embeddings = embedder.embed_texts(texts)
    logger.info("[ingest] Embeddings computed: shape=%s", embeddings.shape)

    # ── Step 6: Add to FAISS index ────────────────────────────────────────────
    store = get_vector_store()
    store.add(all_chunks, embeddings)

    if save_index:
        store.save()
        logger.info("[ingest] FAISS index saved.")

    # ── Step 7: Write Paper + entities/relations to Neo4j ────────────────────
    kg_result = _write_to_neo4j(
        paper_id=paper_id,
        title=title,
        authors=authors,
        year=year,
        keywords=keywords,
        abstract=abstract,
        sections=sections,
    )

    logger.info("[ingest] Done: %s — %d chunks indexed, %d entities, %d relations in KG",
                paper_id, len(all_chunks),
                kg_result.get("entity_count", 0),
                kg_result.get("relation_count", 0))
    return {
        "paper_id": paper_id,
        "title": title,
        "num_chunks": len(all_chunks),
        "num_pages": num_pages,
        "authors": authors,
        "year": year,
        "entity_count": kg_result.get("entity_count", 0),
        "relation_count": kg_result.get("relation_count", 0),
    }


def _safe_extract_metadata(full_text: str) -> dict:
    """
    Try LLM metadata extraction; fall back to empty dict on failure.
    """
    try:
        from pipeline.extraction.entity_extractor import extract_paper_metadata
        meta = extract_paper_metadata(full_text)
        return {
            "title": meta.title,
            "authors": meta.authors,
            "year": meta.year,
            "abstract": meta.abstract,
            "keywords": getattr(meta, "keywords", []),
        }
    except Exception as exc:
        logger.warning("[ingest] Metadata extraction failed: %s", exc)
        return {}


def _write_to_neo4j(
    paper_id: str,
    title: str,
    authors: list,
    year: int | None,
    keywords: list,
    abstract: str,
    sections: list[dict],
) -> dict:
    """
    Write paper node, author nodes, and extracted entities/relations to Neo4j.

    Gracefully skips on any Neo4j / LLM error.

    Returns:
        {"entity_count": int, "relation_count": int}
    """
    try:
        from app.core.neo4j_client import Neo4jClient
    except Exception as exc:
        logger.warning("[ingest] Neo4j unavailable, skipping KG write: %s", exc)
        return {"entity_count": 0, "relation_count": 0}

    entity_count = 0
    relation_count = 0

    # ── 7a: MERGE Paper node ──────────────────────────────────────────────────
    try:
        Neo4jClient.execute_write(
            """
            MERGE (p:Paper {name: $title})
            SET p.paper_id = $paper_id,
                p.year     = $year,
                p.abstract = $abstract,
                p.keywords = $keywords
            """,
            params={
                "title": title,
                "paper_id": paper_id,
                "year": year,
                "abstract": abstract[:1000],
                "keywords": keywords,
            },
        )
        entity_count += 1
    except Exception as exc:
        logger.warning("[ingest] Failed to write Paper node: %s", exc)
        return {"entity_count": entity_count, "relation_count": relation_count}

    # ── 7b: MERGE Author nodes + AUTHORED_BY edges ───────────────────────────
    for author_name in (authors or []):
        try:
            Neo4jClient.execute_write(
                """
                MERGE (a:Author {name: $author})
                WITH a
                MATCH (p:Paper {name: $title})
                MERGE (p)-[:AUTHORED_BY]->(a)
                """,
                params={"author": author_name, "title": title},
            )
            entity_count += 1
            relation_count += 1
        except Exception as exc:
            logger.debug("[ingest] Author write failed for %r: %s", author_name, exc)

    # ── 7c: Entity/relation extraction from each section ─────────────────────
    # Only process first 3 sections to limit LLM cost during ingestion
    from pipeline.extraction.entity_extractor import extract_entities_from_text

    for sec in sections[:3]:
        text_snippet = sec.get("content", "")[:1500]
        if not text_snippet.strip():
            continue
        try:
            extraction = extract_entities_from_text(
                text=text_snippet,
                section_heading=sec.get("heading", ""),
            )

            # Write extracted entities
            for ent in (extraction.entities or []):
                try:
                    Neo4jClient.execute_write(
                        f"""
                        MERGE (n:{_sanitize_label(ent.type)} {{name: $name}})
                        SET n.description = $description
                        """,
                        params={"name": ent.name, "description": ent.description},
                    )
                    entity_count += 1
                except Exception:
                    pass

            # Write extracted relations
            for rel in (extraction.relations or []):
                try:
                    rel_type = _sanitize_rel(rel.relation)
                    Neo4jClient.execute_write(
                        f"""
                        MATCH (src {{name: $source}})
                        MATCH (tgt {{name: $target}})
                        MERGE (src)-[r:{rel_type}]->(tgt)
                        SET r.evidence = $evidence
                        """,
                        params={
                            "source": rel.source,
                            "target": rel.target,
                            "evidence": rel.evidence,
                        },
                    )
                    relation_count += 1
                except Exception:
                    pass

        except Exception as exc:
            logger.debug("[ingest] Entity extraction failed for section %r: %s",
                         sec.get("heading"), exc)

    return {"entity_count": entity_count, "relation_count": relation_count}


def _sanitize_label(label: str) -> str:
    """Return a safe Neo4j node label (whitelist of known types)."""
    _VALID = {"Paper", "Author", "Method", "Metric", "Dataset", "Task", "Organization"}
    return label if label in _VALID else "Entity"


def _sanitize_rel(rel: str) -> str:
    """Return a safe Neo4j relationship type."""
    _VALID = {
        "CITES", "USES_METHOD", "ACHIEVES_METRIC", "AUTHORED_BY",
        "EVALUATED_ON", "BELONGS_TO", "IMPROVES", "COMPARED_WITH",
        "ADDRESSES_TASK",
    }
    return rel if rel in _VALID else "RELATED_TO"


def ingest_directory(
    dir_path: str,
    glob: str = "*.pdf",
    save_index: bool = True,
) -> List[dict]:
    """
    Ingest all PDFs in a directory. Saves the index once at the end.

    Returns:
        List of per-paper summary dicts.
    """
    pdfs = list(Path(dir_path).glob(glob))
    if not pdfs:
        logger.warning("[ingest_directory] No PDFs found in %s", dir_path)
        return []

    results = []
    for i, pdf in enumerate(pdfs):
        logger.info("[ingest_directory] %d/%d: %s", i + 1, len(pdfs), pdf.name)
        result = ingest_pdf(str(pdf), save_index=False)
        results.append(result)

    if save_index:
        from pipeline.embedding.vector_store import get_vector_store
        get_vector_store().save()

    return results
