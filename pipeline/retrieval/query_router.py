"""
Hybrid Retrieval: Query Router

Decides how to weight the KG vs vector retrieval for a given query.
Returns `alpha` ∈ [0.0, 1.0]:
  - 0.0 = rely entirely on Knowledge Graph (Cypher)
  - 1.0 = rely entirely on vector semantic search
  - 0.5 = balanced hybrid

## Routing Strategy (two-stage)

Stage 1 — Fast heuristic (no LLM call):
  Check for signals in the query text that strongly indicate KG or vector need.

  KG-heavy signals (lower alpha):
    - Named entity keywords: paper titles in quotes, author names (et al.),
      method names capitalized, comparison keywords
    - Explicit relationship queries: "uses", "proposes", "cites", "authored by"
    - Structural queries: "how many papers", "list all methods"

  Vector-heavy signals (higher alpha):
    - Broad/conceptual: "what are challenges", "summarize", "explain"
    - Abstract topic queries with no named entities

Stage 2 — LLM refinement (optional, when heuristic is uncertain):
  Ask LLM to classify the query intent.
  Skipped for performance when heuristic gives a clear signal (alpha < 0.2 or > 0.8).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

# ── Heuristic patterns ────────────────────────────────────────────────────────

# Signals that the answer is best found in the KG (structured facts)
_KG_PATTERNS = [
    r"\bet\s+al\b",                          # Author et al.
    r'"[^"]{3,}"',                            # Quoted paper/method name
    r"\b(cites?|cited\s+by|references?)\b",
    r"\b(authored?\s+by|authors?\s+of)\b",
    r"\b(uses?|used|using)\s+\w",            # "uses Transformer"
    r"\b(proposes?|proposed)\b",
    r"\b(improves?|improved)\b",
    r"\b(evaluated?\s+on|datasets?|benchmarks?)\b",
    r"\b(compares?|comparison|versus|vs\.?)\b",
    r"\b(how\s+many|list\s+all|which\s+papers?)\b",
    r"\b(metrics?|accuracy|f1|bleu|rouge)\b",
]

# Signals that the answer needs semantic context (free text understanding)
_VECTOR_PATTERNS = [
    r"\b(summarize|summary|overview|explain|describe)\b",
    r"\b(challenges?|limitations?|drawbacks?|issues?)\b",
    r"\b(trend|progress|state\s+of\s+the\s+art|recent\s+work)\b",
    r"\b(how\s+does|why\s+does|what\s+is\s+the\s+intuition)\b",
    r"\b(difference\s+between|similarities?\s+between)\b",
    r"\b(broad|general|overview)\b",
]

_KG_COMPILED = [re.compile(p, re.IGNORECASE) for p in _KG_PATTERNS]
_VECTOR_COMPILED = [re.compile(p, re.IGNORECASE) for p in _VECTOR_PATTERNS]


@dataclass
class RoutingDecision:
    alpha: float            # 0=KG, 1=vector
    mode: str               # "kg" | "vector" | "hybrid"
    reason: str             # human-readable explanation
    kg_signals: List[str]   # matched KG patterns
    vec_signals: List[str]  # matched vector patterns


def _heuristic_alpha(query: str) -> tuple[float, List[str], List[str]]:
    """
    Return (alpha, kg_signals, vec_signals) purely from regex heuristics.
    """
    kg_hits = [p.pattern for p in _KG_COMPILED if p.search(query)]
    vec_hits = [p.pattern for p in _VECTOR_COMPILED if p.search(query)]

    kg_score = len(kg_hits)
    vec_score = len(vec_hits)
    total = kg_score + vec_score

    if total == 0:
        return 0.5, [], []

    # alpha = fraction of vector signals
    raw_alpha = vec_score / total
    # Dampen extremes slightly to keep some hybrid mixing
    alpha = 0.15 + raw_alpha * 0.70  # maps [0,1] → [0.15, 0.85]
    return round(alpha, 2), kg_hits, vec_hits


class QueryRouter:
    """
    Stateless router that produces a RoutingDecision for a user query.
    """

    def __init__(self, use_llm_refinement: bool = False) -> None:
        """
        Args:
            use_llm_refinement: If True, call LLM for ambiguous queries.
                                 Adds ~0.5–1s latency. Disabled by default.
        """
        self._use_llm = use_llm_refinement

    def route(self, query: str, default_alpha: float = 0.5) -> RoutingDecision:
        """
        Produce a routing decision for *query*.

        Args:
            query:         User's natural-language question.
            default_alpha: Fallback alpha from settings.

        Returns:
            :class:`RoutingDecision`
        """
        alpha, kg_signals, vec_signals = _heuristic_alpha(query)

        # If heuristic is confident, skip LLM
        if not self._use_llm or (alpha < 0.2 or alpha > 0.8):
            mode = _alpha_to_mode(alpha)
            reason = (
                f"Heuristic: {len(kg_signals)} KG signals, {len(vec_signals)} vector signals "
                f"→ alpha={alpha}"
            )
            return RoutingDecision(alpha, mode, reason, kg_signals, vec_signals)

        # LLM refinement for ambiguous queries
        try:
            llm_alpha = _llm_refine(query)
            reason = f"LLM refinement → alpha={llm_alpha} (heuristic was {alpha})"
            alpha = llm_alpha
        except Exception as exc:
            logger.warning("LLM routing failed, using heuristic: %s", exc)
            reason = f"Heuristic fallback (LLM error): alpha={alpha}"

        mode = _alpha_to_mode(alpha)
        return RoutingDecision(alpha, mode, reason, kg_signals, vec_signals)


def _alpha_to_mode(alpha: float) -> str:
    if alpha <= 0.3:
        return "kg"
    if alpha >= 0.7:
        return "vector"
    return "hybrid"


def _llm_refine(query: str) -> float:
    """
    Ask the LLM to rate how much this query needs semantic search (0–10).
    Returns normalised alpha in [0, 1].
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core.llm_client import get_llm

    llm = get_llm()
    prompt = (
        "You are a query-routing expert. Rate how much the following query "
        "benefits from SEMANTIC SEARCH (dense vector) vs STRUCTURED GRAPH LOOKUP (Cypher).\n\n"
        "Return only a single integer 0–10:\n"
        "  0 = fully answered by graph (named entities, relationships)\n"
        " 10 = fully answered by semantic search (conceptual, abstract)\n\n"
        f"Query: {query}"
    )
    response = llm.invoke([
        SystemMessage(content="You are a routing agent."),
        HumanMessage(content=prompt),
    ])
    raw = response.content.strip()
    # Extract first integer from response
    match = re.search(r"\d+", raw)
    if match:
        score = min(10, max(0, int(match.group())))
        return round(score / 10.0, 1)
    return 0.5


# ── Convenience function ──────────────────────────────────────────────────────

_default_router = QueryRouter(use_llm_refinement=False)


def route_query(query: str, default_alpha: float = 0.5) -> RoutingDecision:
    """Module-level convenience wrapper around the default router."""
    return _default_router.route(query, default_alpha=default_alpha)
