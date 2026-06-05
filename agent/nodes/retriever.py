"""
Agent Node: Retriever — Query Neo4j Knowledge Graph lấy context.
"""

import re

from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState

CYPHER_PROMPT = """Bạn là chuyên gia Neo4j Cypher.

Graph Schema:
- Node types: Paper, Author, Organization, Conference, Topic, Task, Methodology, Dataset, Result
- Edge types: AUTHORED, AFFILIATED_WITH, PUBLISHED_AT, COVERS_TOPIC, ADDRESSES_TASK, USES_METHOD, EVALUATED_ON, CITES, ACHIEVES, RESULT_ON, RESULT_WITH, SUBTOPIC_OF, VARIANT_OF, IMPROVES, COMPARED_WITH
- Paper properties: paper_id, name, title, abstract, year, categories, keywords
- Entity properties thường gặp: name, description, aliases
- Result properties: result_id, metric_name, value, unit, context

Viết 1 câu Cypher query để tìm thông tin cần thiết. CHỈ trả về Cypher, luôn LIMIT <= 20."""


def retrieve_from_graph(state: AgentState) -> dict:
    """Node: Dựa trên bước hiện tại trong plan → query Neo4j."""
    from backend.app.core.llm_client import get_llm
    from backend.app.core.neo4j_client import Neo4jClient

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if current_step >= len(plan):
        return {"current_step": current_step}

    step = plan[current_step]
    llm = get_llm()
    top_k = int(state.get("top_k", 5) or 5)
    alpha = float(state.get("alpha", 0.5) or 0.5)

    response = llm.invoke([
        SystemMessage(content=CYPHER_PROMPT),
        HumanMessage(content=f"Bước tìm kiếm: {step}"),
    ])

    cypher = response.content.strip().replace("```cypher", "").replace("```", "").strip()
    cypher = re.sub(r'\."([^"`]+)"', r'.`\1`', cypher)

    context = []
    records = []
    try:
        records = Neo4jClient.execute_query(cypher)
    except Exception as e:
        records = [{"error": str(e), "query": cypher}]

    vector_results = []
    try:
        from pipeline.retrieval.vector_retriever import retrieve_chunks
        vector_results = retrieve_chunks(step, top_k=top_k, refresh=True)
    except Exception as e:
        vector_results = []
        records.append({"vector_error": str(e)})

    try:
        from pipeline.retrieval.fusion import build_llm_context, reciprocal_rank_fusion

        fused = reciprocal_rank_fusion(vector_results, records, alpha=alpha)
        context_text = build_llm_context(fused, query=step, cypher=cypher, max_items=top_k)
    except Exception as e:
        context_text = ""
        records.append({"fusion_error": str(e)})

    context.append(
        {
            "step": step,
            "cypher": cypher,
            "kg_results": records,
            "vector_results": [chunk.to_dict() for chunk in vector_results],
            "hybrid_context": context_text,
        }
    )

    return {
        "retrieved_context": state.get("retrieved_context", []) + context,
        "current_step": current_step + 1,
        "needs_more_info": False,
    }
