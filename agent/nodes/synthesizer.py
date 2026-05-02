"""
Agent Node: Synthesizer

Upgraded from KG-only to hybrid context synthesis.

Prompt structure:
  1. System: role + instructions (cite papers, use markdown)
  2. User:
     - Original question
     - Multi-step plan
     - Fused context block (semantic chunks + KG facts)

The LLM is explicitly instructed to:
  - Cite paper titles from the semantic chunks
  - Use structured facts from the KG for precise claims
  - Clearly separate what it knows from the retrieved context
    vs what it is inferring
"""

from __future__ import annotations

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are an expert research assistant specializing in academic papers.

You have been given:
  1. **Semantic Context** — text chunks retrieved from papers (with titles, authors, sections)
  2. **Structured Facts** — records from a Knowledge Graph (Neo4j) via Cypher queries

Your task: answer the user's question accurately, grounded strictly in the provided context.

Guidelines:
- Write in English using clear, concise markdown.
- **Cite papers** using [Paper Title (Year)] format whenever you use information from a chunk.
- For structured facts (KG results), refer to entities by name.
- If the context is insufficient to fully answer, state clearly what is missing.
- Do NOT hallucinate facts not present in the context.
- Use headings, bullet points, or tables where appropriate for clarity.
- At the end, list sources under a **## Sources** section."""


def synthesize_answer(state: AgentState) -> dict:
    """Node: synthesize final answer from hybrid context."""
    from app.core.llm_client import get_llm

    llm = get_llm()
    user_query: str = state.get("user_query", "")
    plan = state.get("plan", [])
    retrieved_context = state.get("retrieved_context", [])
    vector_chunks = state.get("vector_chunks", [])
    retrieval_mode = state.get("retrieval_mode", "hybrid")
    alpha = state.get("alpha", 0.5)

    # ── Extract pre-built context blocks ─────────────────────────────────────
    # The retriever stores formatted context blocks as {"_context_block": str}
    context_blocks = [
        r["_context_block"]
        for r in retrieved_context
        if isinstance(r, dict) and "_context_block" in r
    ]

    # Fallback: raw KG records (backwards-compatible)
    raw_kg_records = [
        r for r in retrieved_context
        if isinstance(r, dict) and "_context_block" not in r
    ]

    # Compose context string
    context_parts = []

    if context_blocks:
        context_parts.extend(context_blocks)
    elif raw_kg_records:
        context_parts.append("## Knowledge Graph Records")
        context_parts.append(
            json.dumps(raw_kg_records[:20], ensure_ascii=False, indent=2, default=str)
        )

    if not context_blocks and vector_chunks:
        context_parts.append("## Retrieved Paper Chunks")
        for i, chunk in enumerate(vector_chunks[:5], 1):
            context_parts.append(
                f"[{i}] **{chunk.get('title', chunk.get('paper_id', ''))}** "
                f"— {chunk.get('source_section', '')}\n"
                f"{chunk.get('text', '')}"
            )

    context_text = "\n\n".join(context_parts) if context_parts else "*No context retrieved.*"

    # ── Build user message ────────────────────────────────────────────────────
    plan_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(plan))
    meta_line = f"[Retrieval mode: {retrieval_mode} | alpha={alpha:.2f}]"

    user_message = (
        f"**Question:** {user_query}\n\n"
        f"**Reasoning Plan:**\n{plan_text}\n\n"
        f"{meta_line}\n\n"
        f"**Retrieved Context:**\n\n{context_text}"
    )

    response = llm.invoke([
        SystemMessage(content=SYNTHESIS_PROMPT),
        HumanMessage(content=user_message),
    ])

    logger.debug("Synthesizer generated answer (%d chars)", len(response.content))

    return {
        "final_answer": response.content,
        "messages": state.get("messages", []) + [response],
    }
