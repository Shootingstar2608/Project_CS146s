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
from enum import Enum

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
    from backend.app.config import get_settings

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
        full_text=full_text,
        categories=meta.get("categories", ["Uncategorized"]),
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
        logger.info("[ingest] Extracted metadata: %s", meta)
        return {
            "title": meta.title,
            "authors": meta.authors,
            "year": meta.year,
            "categories": [c.value for c in meta.categories] if meta.categories else ["Uncategorized"],
            "abstract": meta.abstract,
            "keywords": getattr(meta, "keywords", []),
        }
    except Exception as exc:
        logger.warning("[ingest] Metadata extraction failed: %s", exc)
        return {}


def _infer_affiliations_from_header(full_text: str, authors: list[str]) -> list[tuple[str, str]]:
    """Infer author -> organization pairs from the PDF header block."""
    if not authors:
        return []

    header_lines = [line.strip() for line in full_text[:3500].splitlines() if line.strip()]
    if not header_lines:
        return []

    org_keywords = (
        "brain",
        "research",
        "university",
        "institute",
        "laboratory",
        "laboratories",
        "lab",
        "labs",
        "college",
        "school",
        "center",
        "centre",
        "department",
        "dept",
        "openai",
        "deepmind",
        "google",
        "microsoft",
        "meta",
        "nvidia",
        "amazon",
        "apple",
        "tencent",
        "baidu",
        "bytedance",
        "berkeley",
        "stanford",
        "mit",
        "oxford",
        "cambridge",
        "toronto",
        "caltech",
        "eth",
    )

    normalized_authors = {author.casefold(): author for author in authors}

    def looks_like_org(line: str) -> bool:
        lowered = line.casefold()
        if "@" in lowered:
            return False
        if len(line.split()) > 10:
            return False
        return any(keyword in lowered for keyword in org_keywords)

    organization_candidates: list[tuple[int, str]] = []
    for index, line in enumerate(header_lines):
        if looks_like_org(line):
            organization_candidates.append((index, line))

    if not organization_candidates:
        return []

    pairs: set[tuple[str, str]] = set()
    for index, org_name in organization_candidates:
        local_authors: set[str] = set()
        for offset in (-2, -1, 0, 1, 2):
            line_index = index + offset
            if line_index < 0 or line_index >= len(header_lines):
                continue
            line = header_lines[line_index].casefold()
            for author_key, author_name in normalized_authors.items():
                if author_key in line:
                    local_authors.add(author_name)

        if local_authors:
            for author_name in local_authors:
                pairs.add((author_name, org_name))
        elif len(organization_candidates) == 1:
            for author_name in authors:
                pairs.add((author_name, org_name))

    return sorted(pairs)


def _write_to_neo4j(
    paper_id: str,
    title: str,
    authors: list,
    year: int | None,
    full_text: str,
    categories: list[str],
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
        from backend.app.core.neo4j_client import Neo4jClient
    except Exception as exc:
        logger.warning("[ingest] Neo4j unavailable, skipping KG write: %s", exc)
        return {"entity_count": 0, "relation_count": 0}

    entity_count = 0
    relation_count = 0

    # ── 7a: MERGE Paper node ──────────────────────────────────────────────────
    try:
        Neo4jClient.execute_write(
            """
            MERGE (p:Paper {paper_id: $paper_id})
            SET p.name       = $title,
                p.year       = $year,
                p.categories = $categories,
                p.abstract   = $abstract,
                p.keywords   = $keywords
            """,
            params={
                "title": title,
                "paper_id": paper_id,
                "year": year,
                "categories": categories,
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
                MATCH (p:Paper {paper_id: $paper_id})
                MERGE (p)-[:AUTHORED_BY]->(a)
                """,
                params={"author": author_name, "paper_id": paper_id},
            )
            entity_count += 1
            relation_count += 1
        except Exception as exc:
            logger.debug("[ingest] Author write failed for %r: %s", author_name, exc)

    affiliations = _infer_affiliations_from_header(full_text, authors or [])
    for author_name, org_name in affiliations:
        try:
            Neo4jClient.execute_write(
                """
                MERGE (o:Organization {name: $organization})
                SET o.description = COALESCE(o.description, $description)
                WITH o
                MATCH (a:Author {name: $author})
                MERGE (a)-[:AFFILIATED_WITH]->(o)
                """,
                params={
                    "author": author_name,
                    "organization": org_name,
                    "description": "Inferred from paper header",
                },
            )
            entity_count += 1
            relation_count += 1
        except Exception as exc:
            logger.debug("[ingest] Affiliation write failed for %r -> %r: %s", author_name, org_name, exc)

    # ── 7c: Result nodes + ACHIEVES edges ────────────────────────────────────

    # ── 7d: Entity/relation extraction from each section ─────────────────────
    # Process all sections (increase snippet length to capture more context for extraction)
    from pipeline.extraction.entity_extractor import extract_entities_from_text

    for sec in sections:
        text_snippet = sec.get("content", "")[:4000]
        if not text_snippet.strip():
            continue
        try:
            extraction = extract_entities_from_text(
                text=text_snippet,
                section_heading=sec.get("heading", ""),
            )

            # Write extracted Result nodes first so ACHIEVES edges can target them later.
            for res in (extraction.results or []):
                try:
                    Neo4jClient.execute_write(
                        """
                        MERGE (n:Result {result_id: $result_id})
                        SET n.metric_name = $metric_name,
                            n.value = $value,
                            n.unit = $unit,
                            n.context = $context,
                            n.is_sota = $is_sota
                        """,
                        params={
                            "result_id": res.entity_id,
                            "metric_name": res.metric_name,
                            "value": res.value,
                            "unit": res.unit,
                            "context": res.context,
                            "is_sota": res.is_sota,
                        },
                    )
                    entity_count += 1
                except Exception:
                    pass

            # Automatically connect the paper to each extracted result.
            for res in (extraction.results or []):
                try:
                    Neo4jClient.execute_write(
                        """
                        MATCH (p:Paper {paper_id: $paper_id})
                        MATCH (r:Result {result_id: $result_id})
                        MERGE (p)-[:ACHIEVES]->(r)
                        """,
                        params={"paper_id": paper_id, "result_id": res.entity_id},
                    )
                    relation_count += 1
                except Exception:
                    pass

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


def _sanitize_label(label: str | Enum) -> str:
    """Return a safe Neo4j node label (whitelist of known types)."""
    _VALID = {
        "Paper",
        "Author",
        "Organization",
        "Conference",
        "Topic",
        "Task",
        "Methodology",
        "Dataset",
        "Result",
    }
    val = label.value if hasattr(label, "value") else str(label)
    return val if val in _VALID else "Entity"


def _sanitize_rel(rel: str | Enum) -> str:
    """Return a safe Neo4j relationship type."""
    _VALID = {
        "AUTHORED",
        "AFFILIATED_WITH",
        "PUBLISHED_AT",
        "COVERS_TOPIC",
        "ADDRESSES_TASK",
        "USES_METHOD",
        "EVALUATED_ON",
        "CITES",
        "ACHIEVES",
        "SUBTOPIC_OF",
        "VARIANT_OF",
        "IMPROVES",
        "COMPARED_WITH",
        "RESULT_ON",
        "RESULT_WITH",
    }
    val = rel.value if hasattr(rel, "value") else str(rel)
    return val if val in _VALID else "RELATED_TO"


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
