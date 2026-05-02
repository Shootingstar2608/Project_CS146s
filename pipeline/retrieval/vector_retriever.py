"""
Hybrid Retrieval: Vector Retriever

Converts a user query → embedding → FAISS search → ranked Chunk list.

Usage::

    chunks = retrieve_chunks("What datasets does BERT use?", top_k=5)
    for c in chunks:
        print(c.score, c.title, c.text[:80])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved chunk annotated with its cosine similarity score."""

    chunk_id: str
    paper_id: str
    text: str
    source_section: str
    title: str
    authors: List[str]
    year: int | None
    chunk_index: int
    score: float           # cosine similarity ∈ [-1, 1] (L2-normed → [0, 1])

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "paper_id": self.paper_id,
            "text": self.text,
            "source_section": self.source_section,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "chunk_index": self.chunk_index,
            "score": round(self.score, 4),
        }


def retrieve_chunks(
    query: str,
    top_k: int = 5,
) -> List[RetrievedChunk]:
    """
    Embed *query* and return the top-k most similar chunks from the FAISS index.

    Args:
        query:  User question or search string.
        top_k:  Maximum number of chunks to return.

    Returns:
        List of :class:`RetrievedChunk`, sorted by cosine similarity descending.
        Returns [] if the index is empty.
    """
    from pipeline.embedding.embedder import get_embedder
    from pipeline.embedding.vector_store import get_vector_store

    embedder = get_embedder()
    store = get_vector_store()

    if store.size == 0:
        logger.warning("VectorStore is empty. Run the ingest pipeline first.")
        return []

    query_vec = embedder.embed_query(query)
    raw_results = store.search(query_vec, top_k=top_k)

    chunks: List[RetrievedChunk] = []
    for meta, score in raw_results:
        chunk = RetrievedChunk(
            chunk_id=meta.get("chunk_id", ""),
            paper_id=meta.get("paper_id", ""),
            text=meta.get("text", ""),
            source_section=meta.get("source_section", ""),
            title=meta.get("title", ""),
            authors=meta.get("authors", []),
            year=meta.get("year"),
            chunk_index=meta.get("chunk_index", 0),
            score=score,
        )
        chunks.append(chunk)

    logger.debug(
        "Vector retrieval: query=%r  top_k=%d  returned=%d",
        query[:60],
        top_k,
        len(chunks),
    )
    return chunks
