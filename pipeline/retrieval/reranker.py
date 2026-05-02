"""
Hybrid Retrieval: Cross-Encoder Re-ranker (Bonus)

Uses a cross-encoder model to re-score the top-N candidates from the
fused result list and return the top-K most relevant.

Cross-encoders read (query, passage) pairs jointly — much more accurate
than bi-encoder cosine similarity but too slow to scan the full index.
The typical pattern is:
    bi-encoder → top-20 candidates → cross-encoder → top-5

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  - ~67 MB, fast CPU inference (~100ms for 20 pairs)
  - Trained on MS MARCO passage ranking
  - MIT license

Activation: set RERANK_ENABLED=true in .env
"""

from __future__ import annotations

import logging
from typing import List

from pipeline.retrieval.fusion import FusedResult

logger = logging.getLogger(__name__)


def rerank(
    query: str,
    candidates: List[FusedResult],
    top_n: int | None = None,
    model_name: str | None = None,
) -> List[FusedResult]:
    """
    Re-rank *candidates* using a cross-encoder model.

    Args:
        query:      User query string.
        candidates: Fused results to re-rank (typically top-20).
        top_n:      How many to keep after re-ranking (defaults to settings).
        model_name: Cross-encoder model name (defaults to settings).

    Returns:
        Re-ranked and truncated list of :class:`FusedResult`.
        If RERANK_ENABLED is False or the model fails to load, returns
        *candidates* unchanged.
    """
    from app.config import get_settings

    cfg = get_settings()

    if not cfg.rerank_enabled:
        logger.debug("Re-ranking disabled (RERANK_ENABLED=false)")
        return candidates

    top_n = top_n or cfg.rerank_top_n
    model_name = model_name or cfg.rerank_model

    if not candidates:
        return candidates

    # Build (query, passage_text) pairs
    pairs: List[tuple[str, str]] = []
    for item in candidates:
        if item.chunk:
            text = item.chunk.text
        elif item.kg_record:
            import json
            text = json.dumps(item.kg_record, ensure_ascii=False, default=str)
        else:
            text = ""
        pairs.append((query, text))

    try:
        from sentence_transformers import CrossEncoder
        model = _get_cross_encoder(model_name)
        scores = model.predict(pairs)
    except ImportError:
        logger.warning(
            "sentence-transformers not installed — skipping re-ranking. "
            "Run: pip install sentence-transformers"
        )
        return candidates[:top_n]
    except Exception as exc:
        logger.error("Re-ranking failed: %s — returning fused order", exc)
        return candidates[:top_n]

    # Attach scores and sort
    scored = sorted(
        zip(scores, candidates),
        key=lambda x: -x[0],
    )
    reranked = [item for _, item in scored[:top_n]]

    logger.debug(
        "Re-ranking: %d candidates → %d kept  (model=%s)",
        len(candidates),
        len(reranked),
        model_name,
    )
    return reranked


# ── Model cache ───────────────────────────────────────────────────────────────

_cross_encoder_cache: dict = {}


def _get_cross_encoder(model_name: str):
    """Lazy-load and cache the cross-encoder model."""
    if model_name not in _cross_encoder_cache:
        from sentence_transformers import CrossEncoder
        logger.info("Loading CrossEncoder: %s", model_name)
        _cross_encoder_cache[model_name] = CrossEncoder(model_name)
    return _cross_encoder_cache[model_name]
