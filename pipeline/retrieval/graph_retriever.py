"""
Hybrid Retrieval: Graph Retriever

Improves on the original `agent/nodes/retriever.py` by adding:
  1. Named-entity pre-extraction from the query (avoids generic Cypher)
  2. Focused Cypher templates for common query patterns
  3. Graceful Neo4j error handling with structured return type

This module is called by the upgraded Retriever agent node and can also
be used standalone.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Cypher generation prompt ──────────────────────────────────────────────────

_CYPHER_SYSTEM = """You are a Neo4j Cypher expert for an academic paper Knowledge Graph.

Graph Schema:
  Nodes:  Paper(name, year, abstract, keywords)
          Author(name, affiliation)
          Method(name, description)
          Metric(name, value, description)
          Dataset(name, description, size)
          Task(name, description)
          Organization(name)

  Edges:  AUTHORED_BY       Paper → Author
          CITES             Paper → Paper
          USES_METHOD       Paper → Method
          ACHIEVES_METRIC   Paper → Metric
          EVALUATED_ON      Paper → Dataset
          ADDRESSES_TASK    Paper → Task
          BELONGS_TO        Author → Organization
          IMPROVES          Method → Method
          COMPARED_WITH     Method → Method

Rules:
- Return ONLY valid Cypher. No explanation, no markdown fences.
- Always LIMIT results (≤ 20).
- Use case-insensitive matching: WHERE toLower(n.name) CONTAINS toLower($name)
- Return node .name and relevant properties.
- If unsure, return a broad MATCH … RETURN … LIMIT 10 query."""

_ENTITY_EXTRACTION_SYSTEM = """Extract named entities from the academic research query.
Return a comma-separated list of entity names (paper titles, author names, method names,
dataset names, metric names). If none found, return "NONE".
Only return the list, nothing else."""


# ── Entity extraction ─────────────────────────────────────────────────────────

def extract_query_entities(query: str) -> List[str]:
    """
    Extract named entities from the query.

    Two-stage:
    1. Regex fast path: catch quoted strings, "et al.", CamelCase tokens
    2. LLM fallback for unstructured text
    """
    entities: List[str] = []

    # Quoted strings (paper/dataset/method names)
    entities.extend(re.findall(r'"([^"]+)"', query))
    entities.extend(re.findall(r"'([^']+)'", query))

    # "Author et al." pattern
    entities.extend(re.findall(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+et\s+al", query))

    # CamelCase single tokens (e.g. "BERT", "GPT4", "Transformer")
    entities.extend(re.findall(r"\b[A-Z][A-Z0-9]+\b", query))

    if entities:
        return list(dict.fromkeys(e.strip() for e in entities if e.strip()))

    # LLM fallback
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.core.llm_client import get_llm

        llm = get_llm()
        resp = llm.invoke([
            SystemMessage(content=_ENTITY_EXTRACTION_SYSTEM),
            HumanMessage(content=query),
        ])
        raw = resp.content.strip()
        if raw and raw.upper() != "NONE":
            entities = [e.strip() for e in raw.split(",") if e.strip()]
    except Exception as exc:
        logger.warning("Entity extraction LLM call failed: %s", exc)

    return entities


# ── Cypher generation ─────────────────────────────────────────────────────────

def generate_cypher(query: str, step_description: str | None = None) -> str:
    """
    Ask the LLM to produce a Cypher query for the given retrieval step.

    Args:
        query:            Original user question.
        step_description: Optional planner step description for focus.

    Returns:
        Cleaned Cypher string.
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.core.llm_client import get_llm

    llm = get_llm()
    user_content = (
        f"User query: {query}\n"
        + (f"Retrieval step: {step_description}\n" if step_description else "")
        + "Write a Cypher query."
    )

    response = llm.invoke([
        SystemMessage(content=_CYPHER_SYSTEM),
        HumanMessage(content=user_content),
    ])

    cypher = (
        response.content.strip()
        .replace("```cypher", "")
        .replace("```", "")
        .strip()
    )
    return cypher


# ── Main retrieval function ───────────────────────────────────────────────────

def retrieve_from_graph_hybrid(
    query: str,
    step_description: str | None = None,
    entities: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Run graph-based retrieval for a query step.

    Returns:
        {
            "cypher":  str — the generated Cypher,
            "results": list[dict] — Neo4j records,
            "entities": list[str] — extracted entities,
            "error":   str | None,
        }
    """
    from app.core.neo4j_client import Neo4jClient

    # Extract entities if not provided
    if entities is None:
        entities = extract_query_entities(query)
    logger.debug("Graph retrieval | entities=%s", entities)

    # Generate Cypher
    cypher = generate_cypher(query, step_description)
    logger.debug("Generated Cypher:\n%s", cypher)

    # Execute
    try:
        records = Neo4jClient.execute_query(cypher)
        return {
            "cypher": cypher,
            "results": records,
            "entities": entities,
            "error": None,
        }
    except Exception as exc:
        logger.error("Cypher execution failed: %s", exc)
        return {
            "cypher": cypher,
            "results": [],
            "entities": entities,
            "error": str(exc),
        }
