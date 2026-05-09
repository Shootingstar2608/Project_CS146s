"""
Embedding Pipeline: Chunker

Splits text into overlapping fixed-size character chunks, each carrying
rich metadata so the retriever can trace a chunk back to its source paper.

Design choices
--------------
* Character-based (not token-based) to stay dependency-free and
  language-agnostic for Vietnamese / English mixed content.
* chunk_size=512 / overlap=64 are good defaults for academic text —
  override via Settings if needed.
* Section heading is preserved in each chunk for better retrieval context.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List


@dataclass
class Chunk:
    """A single text chunk linked to its source paper."""

    chunk_id: str          # stable sha256-based ID
    paper_id: str          # opaque paper identifier (e.g. filename or DB id)
    text: str              # chunk content
    source_section: str    # section heading (e.g. "Introduction")
    title: str = ""        # paper title from metadata
    authors: List[str] = field(default_factory=list)
    year: int | None = None
    chunk_index: int = 0   # 0-based position within the paper

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
        }


def _make_chunk_id(paper_id: str, chunk_index: int, text: str) -> str:
    """Deterministic SHA-256 chunk ID."""
    raw = f"{paper_id}::{chunk_index}::{text[:64]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[str]:
    """
    Split *text* into overlapping chunks of at most *chunk_size* characters.

    Returns:
        List of chunk strings (may be fewer than expected for short text).
    """
    if not text:
        return []

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap  # slide back by overlap

    return chunks


def chunk_section(
    section_heading: str,
    section_text: str,
    paper_id: str,
    paper_title: str = "",
    authors: List[str] | None = None,
    year: int | None = None,
    global_chunk_offset: int = 0,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[Chunk]:
    """
    Chunk a single section and return a list of :class:`Chunk` objects.

    Args:
        section_heading:    E.g. "2.1 Related Work"
        section_text:       Raw section text (already cleaned by pdf_parser)
        paper_id:           Unique paper identifier
        paper_title:        Paper title for metadata
        authors:            List of author names
        year:               Publication year
        global_chunk_offset: Starting chunk_index (for multi-section papers)
        chunk_size:         Characters per chunk
        overlap:            Overlap between consecutive chunks

    Returns:
        List of :class:`Chunk` objects.
    """
    authors = authors or []
    raw_chunks = chunk_text(section_text, chunk_size=chunk_size, overlap=overlap)

    result: List[Chunk] = []
    for i, raw in enumerate(raw_chunks):
        idx = global_chunk_offset + i
        # Prepend section heading so that each chunk has standalone context
        enriched_text = f"[{section_heading}]\n{raw}" if section_heading else raw
        chunk = Chunk(
            chunk_id=_make_chunk_id(paper_id, idx, raw),
            paper_id=paper_id,
            text=enriched_text,
            source_section=section_heading,
            title=paper_title,
            authors=authors,
            year=year,
            chunk_index=idx,
        )
        result.append(chunk)

    return result
