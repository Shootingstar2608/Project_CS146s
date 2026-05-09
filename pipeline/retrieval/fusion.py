"""
Hybrid Retrieval: RRF Fusion + Prompt Context Builder

## Reciprocal Rank Fusion (RRF)

Given two ranked lists (vector results, KG results), RRF produces a
single unified ranking by combining per-item reciprocal ranks:

    score(d) = Σ_i  1 / (k + rank_i(d))

where k=60 is a constant that dampens the influence of high-rank items
(Cormack et al., 2009). The constant is configurable via settings.

## Alpha Weighting

We apply alpha weighting on top of RRF so the query router can shift
influence toward one modality:

    score(d) = (1 - alpha) * rrf_kg(d) + alpha * rrf_vec(d)

alpha=0 → pure KG, alpha=1 → pure vector, alpha=0.5 → balanced.

## Context Formatting

`build_llm_context()` formats the fused results into a structured prompt
block that the Synthesizer node feeds to the LLM.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from pipeline.retrieval.vector_retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class FusedResult:
    """A single item in the fused result list."""

    item_id: str          # chunk_id or KG record hash
    source: str           # "vector" | "kg" | "both"
    rrf_score: float
    chunk: RetrievedChunk | None = None   # populated for vector hits
    kg_record: Dict[str, Any] | None = None  # populated for KG hits
    title: str = ""


def reciprocal_rank_fusion(
    vector_results: List[RetrievedChunk],
    kg_results: List[Dict[str, Any]],
    alpha: float = 0.5,
    k: int = 60,
) -> List[FusedResult]:
    """
    Merge vector and KG results via RRF with alpha weighting.

    Args:
        vector_results: Ordered list of RetrievedChunk (best first).
        kg_results:     Ordered list of KG dicts (best first, as returned by Neo4j).
        alpha:          Vector weight [0, 1].
        k:              RRF constant (default 60).

    Returns:
        List of :class:`FusedResult` sorted by descending fused score.
    """
    scores: Dict[str, float] = {}
    items: Dict[str, FusedResult] = {}

    # ── Vector side ───────────────────────────────────────────────────────────
    vec_weight = alpha
    for rank, chunk in enumerate(vector_results, start=1):
        item_id = f"vec::{chunk.chunk_id}"
        rrf = vec_weight * (1.0 / (k + rank))
        scores[item_id] = scores.get(item_id, 0.0) + rrf
        items[item_id] = FusedResult(
            item_id=item_id,
            source="vector",
            rrf_score=0.0,
            chunk=chunk,
            title=chunk.title,
        )

    # ── KG side ───────────────────────────────────────────────────────────────
    kg_weight = 1.0 - alpha
    for rank, record in enumerate(kg_results, start=1):
        item_id = f"kg::{_record_id(record, rank)}"
        rrf = kg_weight * (1.0 / (k + rank))
        scores[item_id] = scores.get(item_id, 0.0) + rrf
        items[item_id] = FusedResult(
            item_id=item_id,
            source="kg",
            rrf_score=0.0,
            kg_record=record,
            title=_record_title(record),
        )

    # ── Assign scores and sort ────────────────────────────────────────────────
    result: List[FusedResult] = []
    for item_id, score in sorted(scores.items(), key=lambda x: -x[1]):
        item = items[item_id]
        item.rrf_score = score
        result.append(item)

    return result


def _record_id(record: Dict[str, Any], fallback_rank: int) -> str:
    """Create a stable string key for a KG record."""
    name = record.get("name") or record.get("p.name") or str(fallback_rank)
    return str(name)[:64]


def _record_title(record: Dict[str, Any]) -> str:
    for key in ("name", "p.name", "title"):
        if record.get(key):
            return str(record[key])
    return ""


# ── Convenience wrapper ───────────────────────────────────────────────────────

def fuse_results(
    vector_results: List[RetrievedChunk],
    kg_results: List[Dict[str, Any]],
    alpha: float = 0.5,
) -> List[FusedResult]:
    """Fuse with settings-default k."""
    from app.config import get_settings
    k = get_settings().rrf_k
    return reciprocal_rank_fusion(vector_results, kg_results, alpha=alpha, k=k)


# ── LLM Context Formatter ─────────────────────────────────────────────────────

def build_llm_context(
    fused: List[FusedResult],
    query: str,
    cypher: str = "",
    max_items: int = 10,
) -> str:
    """
    Format fused results into a structured string for the LLM prompt.

    Structure:
        ## Semantic Context (from papers)
        [1] Title — Section (score=0.87)
        <text>

        ## Structured Facts (from Knowledge Graph)
        Cypher: ...
        [1] {record}
        ...

    Args:
        fused:     Output of :func:`fuse_results`.
        query:     Original user query (for context).
        cypher:    The Cypher query that produced KG results.
        max_items: Max total items to include.

    Returns:
        Formatted context string.
    """
    vector_items = [r for r in fused if r.source == "vector" and r.chunk][:max_items]
    kg_items = [r for r in fused if r.source == "kg" and r.kg_record][:max_items]

    parts: List[str] = []

    # ── Semantic chunks ───────────────────────────────────────────────────────
    if vector_items:
        parts.append("## Semantic Context (retrieved paper chunks)")
        for i, item in enumerate(vector_items, start=1):
            c = item.chunk
            authors_str = ", ".join(c.authors[:3]) if c.authors else "Unknown"
            year_str = f" ({c.year})" if c.year else ""
            header = f"[{i}] **{c.title or c.paper_id}**{year_str} — {c.source_section}"
            parts.append(f"{header}  (cosine={c.score:.3f})")
            parts.append(c.text)
            parts.append(f"    *Authors: {authors_str}*")
            parts.append("")

    # ── KG records ───────────────────────────────────────────────────────────
    if kg_items:
        parts.append("## Structured Facts (Knowledge Graph)")
        if cypher:
            parts.append(f"Cypher: `{cypher}`")
        for i, item in enumerate(kg_items, start=1):
            parts.append(
                f"[{i}] {json.dumps(item.kg_record, ensure_ascii=False, default=str)}"
            )
        parts.append("")

    if not parts:
        parts.append("*No context retrieved.*")

    return "\n".join(parts)
