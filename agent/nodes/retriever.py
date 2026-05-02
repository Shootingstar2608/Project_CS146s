"""
Agent Node: Hybrid Retriever

Replaces the KG-only retriever with the full hybrid pipeline:

  1. Query Router    → compute alpha (KG vs vector weight)
  2. Vector Retriever → top-k chunks from FAISS
  3. Graph Retriever  → Cypher → Neo4j structured facts
  4. RRF Fusion       → merged, ranked context
  5. Optional Rerank  → cross-encoder refinement
  6. Context Builder  → formatted prompt block

All intermediate results are stored in AgentState so the Synthesizer
can reference both raw chunks (for citation) and KG facts (for reasoning).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent.state import AgentState

logger = logging.getLogger(__name__)


def retrieve_from_graph(state: AgentState) -> Dict[str, Any]:
    """
    Hybrid Retriever node.

    Reads the current plan step from state, runs both vector and graph
    retrieval, fuses the results, and updates state.

    Returns:
        Partial state update dict consumed by LangGraph.
    """
    from app.config import get_settings
    from pipeline.retrieval.query_router import route_query
    from pipeline.retrieval.vector_retriever import retrieve_chunks
    from pipeline.retrieval.graph_retriever import retrieve_from_graph_hybrid
    from pipeline.retrieval.fusion import fuse_results, build_llm_context
    from pipeline.retrieval.reranker import rerank

    cfg = get_settings()
    plan: List[str] = state.get("plan", [])
    current_step: int = state.get("current_step", 0)

    if current_step >= len(plan):
        return {"current_step": current_step}

    step_description = plan[current_step]
    user_query: str = state.get("user_query", "")

    # ── Step 1: Route query ───────────────────────────────────────────────────
    alpha_override = state.get("alpha_override")
    if alpha_override is not None:
        alpha = float(alpha_override)
        mode = "hybrid" if 0.2 < alpha < 0.8 else ("vector" if alpha >= 0.8 else "kg")
        logger.debug("Alpha override from API: %.2f  mode=%s", alpha, mode)
    else:
        routing = route_query(user_query, default_alpha=cfg.hybrid_alpha)
        alpha = routing.alpha
        mode = routing.mode
        logger.debug(
            "Router: alpha=%.2f  mode=%s  reason=%s",
            alpha,
            mode,
            routing.reason,
        )

    # ── Step 2: Vector retrieval ──────────────────────────────────────────────
    vector_chunks = []
    if alpha > 0.05:  # skip if mode is pure KG
        top_k = cfg.vector_top_k
        vector_chunks = retrieve_chunks(user_query, top_k=top_k)
        logger.debug("Vector retrieved %d chunks", len(vector_chunks))

    # ── Step 3: Graph retrieval ───────────────────────────────────────────────
    kg_result: Dict[str, Any] = {"results": [], "cypher": "", "entities": [], "error": None}
    if alpha < 0.95:  # skip if mode is pure vector
        kg_result = retrieve_from_graph_hybrid(
            query=user_query,
            step_description=step_description,
        )
        logger.debug(
            "Graph retrieved %d records  cypher=%r",
            len(kg_result["results"]),
            kg_result["cypher"][:80] if kg_result["cypher"] else "",
        )

    # ── Step 4: Fuse ──────────────────────────────────────────────────────────
    fused = fuse_results(vector_chunks, kg_result["results"], alpha=alpha)

    # ── Step 5: Optional rerank ───────────────────────────────────────────────
    if cfg.rerank_enabled and fused:
        fused = rerank(user_query, fused)

    # ── Step 6: Build context block ───────────────────────────────────────────
    context_text = build_llm_context(
        fused=fused,
        query=user_query,
        cypher=kg_result.get("cypher", ""),
    )

    # ── Merge into state ──────────────────────────────────────────────────────
    prior_context: List[dict] = state.get("retrieved_context", [])
    prior_chunks: List[dict] = state.get("vector_chunks", [])

    new_kg_records = kg_result["results"]
    new_chunk_dicts = [c.to_dict() for c in vector_chunks]

    # Build graph_data for visualization
    graph_nodes = list({r.get("name", "") for r in new_kg_records if r.get("name")})
    prior_graph = state.get("graph_data", {"nodes": [], "edges": []})

    return {
        "retrieved_context": prior_context + new_kg_records + [{"_context_block": context_text}],
        "vector_chunks": prior_chunks + new_chunk_dicts,
        "current_step": current_step + 1,
        "needs_more_info": False,
        "retrieval_mode": mode,
        "alpha": alpha,
        "graph_data": {
            "nodes": prior_graph.get("nodes", []) + graph_nodes,
            "edges": prior_graph.get("edges", []),
        },
    }
