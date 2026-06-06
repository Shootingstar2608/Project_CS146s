"""
Agent Graph — LangGraph StateGraph definition.

Luồng: Plan → Retrieve (loop) → Synthesize → END
"""

import sys
import os
from typing import Any

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.planner import plan_steps
from agent.nodes.retriever import retrieve_from_graph
from agent.nodes.synthesizer import synthesize_answer


def should_continue(state: AgentState) -> str:
    """Router: còn bước trong plan → retrieve tiếp, hết → synthesize."""
    current = state.get("current_step", 0)
    plan = state.get("plan", [])

    if current < len(plan):
        return "retrieve"
    return "synthesize"


def build_agent_graph():
    """
    Xây dựng Agent graph:

    Plan → Retrieve ←(loop)→ Retrieve → Synthesize → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("planner_node", plan_steps)
    graph.add_node("retrieve", retrieve_from_graph)
    graph.add_node("synthesize", synthesize_answer)

    graph.set_entry_point("planner_node")

    # Sau plan → đi retrieve bước đầu tiên
    graph.add_edge("planner_node", "retrieve")

    # Sau retrieve → kiểm tra còn bước nào trong plan không
    graph.add_conditional_edges("retrieve", should_continue, {
        "retrieve": "retrieve",
        "synthesize": "synthesize",
    })

    graph.add_edge("synthesize", END)

    return graph.compile()


# Compile graph 1 lần duy nhất
agent_executor = build_agent_graph()


def _can_use_local_fallback(exc: Exception) -> bool:
    message = str(exc)
    return (
        "GROQ_API_KEY is not set" in message
        or "Connection refused" in message
        or "Failed to connect" in message
    )


def _truncate(text: str, limit: int = 420) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _get_paper_records(limit: int = 20) -> list[dict[str, Any]]:
    try:
        from backend.app.core.neo4j_client import Neo4jClient

        return Neo4jClient.execute_query(
            """
            MATCH (p:Paper)
            OPTIONAL MATCH (p)<-[:AUTHORED]-(a:Author)
            RETURN p.paper_id AS paper_id,
                   coalesce(p.name, p.title, p.paper_id) AS title,
                   p.year AS year,
                   p.abstract AS abstract,
                   p.categories AS categories,
                   collect(DISTINCT a.name) AS authors
            LIMIT $limit
            """,
            {"limit": limit},
        )
    except Exception:
        return []


def _build_fallback_graph_data(chunks: list[Any], papers: list[dict[str, Any]]) -> dict:
    nodes_by_id: dict[str, dict[str, Any]] = {}

    for paper in papers:
        paper_id = str(paper.get("paper_id") or "")
        if not paper_id:
            continue
        nodes_by_id[paper_id] = {
            "id": paper_id,
            "label": paper.get("title") or paper_id,
            "type": "Paper",
            "kind": "paper",
            "properties": {
                "authors": paper.get("authors") or [],
                "year": paper.get("year"),
                "categories": paper.get("categories") or [],
                "abstract": paper.get("abstract") or "",
            },
        }

    for chunk in chunks:
        paper_id = getattr(chunk, "paper_id", "")
        if not paper_id or paper_id in nodes_by_id:
            continue
        nodes_by_id[paper_id] = {
            "id": paper_id,
            "label": getattr(chunk, "title", "") or paper_id,
            "type": "Paper",
            "kind": "paper",
            "properties": {
                "authors": getattr(chunk, "authors", []) or [],
                "year": getattr(chunk, "year", None),
                "source_section": getattr(chunk, "source_section", ""),
            },
        }

    return {"nodes": list(nodes_by_id.values()), "edges": [], "links": []}


async def _run_local_retrieval_fallback(
    user_query: str,
    top_k: int,
    reason: Exception,
) -> dict:
    """Fallback when LLM is unavailable: try graph first, then vector."""
    # Try Neo4j graph first
    papers = _get_paper_records(limit=max(top_k, 10))

    if papers:
        paper_lines = []
        for index, paper in enumerate(papers[:top_k], start=1):
            title = paper.get("title") or paper.get("paper_id") or "Untitled paper"
            abstract = _truncate(paper.get("abstract") or "No abstract stored.", 220)
            authors = ", ".join(paper.get("authors") or []) or "Unknown"
            paper_lines.append(f"{index}. **{title}** ({paper.get('year', 'n/a')}) — {authors}\n   {abstract}")
        answer = (
            "No LLM provider is configured. I retrieved the following papers directly "
            "from the Knowledge Graph (Neo4j):\n\n"
            + "\n".join(paper_lines)
        )
        reasoning_steps = [
            "Detected unavailable LLM provider; switched to graph fallback.",
            "Queried Neo4j Knowledge Graph for paper nodes.",
            f"Found {len(papers)} papers in the graph.",
            f"Fallback reason: {reason}",
        ]
    else:
        # Graph empty, try vector
        from pipeline.retrieval.vector_retriever import retrieve_chunks
        chunks = retrieve_chunks(user_query, top_k=top_k, refresh=True)
        if chunks:
            evidence_lines = []
            for index, chunk in enumerate(chunks, start=1):
                title = getattr(chunk, "title", "") or getattr(chunk, "paper_id", "") or "Untitled paper"
                section = getattr(chunk, "source_section", "") or "retrieved section"
                evidence_lines.append(f"{index}. {title} ({section}): {_truncate(getattr(chunk, 'text', ''))}")
            answer = (
                "No LLM provider configured and graph is empty. "
                "Used vector search supplementary fallback:\n\n"
                + "\n".join(evidence_lines)
            )
        else:
            answer = (
                "No LLM provider is configured, and no indexed papers were found yet. "
                "Upload a PDF and wait for indexing to complete, then ask again."
            )
        reasoning_steps = [
            "Detected unavailable LLM provider.",
            "Tried Neo4j Knowledge Graph — no papers found.",
            "Fell back to FAISS vector search.",
            f"Fallback reason: {reason}",
        ]
        chunks = chunks if papers else []
        papers = papers or []

    return {
        "answer": answer,
        "reasoning_steps": reasoning_steps,
        "graph_data": _build_fallback_graph_data([], papers),
    }


async def run_agent(
    user_query: str,
    alpha_override: float | None = None,
    top_k: int = 5,
) -> dict:
    """
    Entry point: chạy Agent cho 1 câu hỏi.

    Args:
        user_query:     Câu hỏi đã được sanitize từ router_chat.
        alpha_override: Tỷ lệ ưu tiên vector retrieval (0.0=graph-only, 1.0=vector-only).
                        None → dùng giá trị cân bằng của retriever (0.5).
        top_k:          Số kết quả tối đa mỗi retriever trả về.
    """
    initial_state = {
        "messages": [],
        "user_query": user_query,
        "plan": [],
        "current_step": 0,
        "retrieved_context": [],
        "final_answer": "",
        "graph_data": {"nodes": [], "edges": []},
        "needs_more_info": False,
        # Graph-first hybrid retrieval params — alpha=0.2 → 80% KG, 20% vector
        "alpha": alpha_override if alpha_override is not None else 0.2,
        "top_k": top_k,
    }

    try:
        result = await agent_executor.ainvoke(initial_state)
    except Exception as exc:
        if _can_use_local_fallback(exc):
            return await _run_local_retrieval_fallback(user_query, top_k, exc)
        raise

    return {
        "answer": result.get("final_answer", ""),
        "reasoning_steps": result.get("plan", []),
        "graph_data": result.get("graph_data", {}),
    }
