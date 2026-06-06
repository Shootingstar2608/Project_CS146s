"""
Agent Node: Retriever — Graph-first retrieval theo đúng yêu cầu đề bài.

Chiến lược:
  1. PRIMARY: Query Neo4j Knowledge Graph (LLM sinh Cypher)
  2. SUPPLEMENTARY: Chỉ dùng FAISS vector search nếu graph trả về < 3 records
  3. Fusion alpha=0.2 → KG chiếm 80%, vector chỉ 20%

Lý do: Đề bài yêu cầu "Không chấp nhận chunking thuần túy.
Bắt buộc trích xuất Entities và Relations." (50% trọng số)
"""

import re

from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState

CYPHER_PROMPT = """Bạn là chuyên gia Neo4j Cypher cho hệ thống Knowledge Graph nghiên cứu khoa học.

Graph Schema:
- Node types: Paper, Author, Organization, Conference, Topic, Task, Methodology, Dataset, Result
- Edge types: AUTHORED, AFFILIATED_WITH, PUBLISHED_AT, COVERS_TOPIC, ADDRESSES_TASK,
              USES_METHOD, EVALUATED_ON, CITES, ACHIEVES, RESULT_ON, RESULT_WITH,
              SUBTOPIC_OF, VARIANT_OF, IMPROVES, COMPARED_WITH
- Paper properties: paper_id, name, abstract, year, categories, keywords
- Author properties: name, aliases
- Methodology properties: name, description, aliases
- Dataset properties: name, description, aliases
- Result properties: result_id, metric_name, value, unit, context, is_sota

Viết 1 câu Cypher query để tìm thông tin cần thiết.
CHỈ trả về Cypher, không giải thích, luôn LIMIT <= 20.
Dùng case-insensitive: WHERE toLower(n.name) CONTAINS toLower($keyword)"""


def _generate_cypher(step: str, llm) -> str:
    """LLM sinh Cypher query từ retrieval step."""
    response = llm.invoke([
        SystemMessage(content=CYPHER_PROMPT),
        HumanMessage(content=f"Bước tìm kiếm: {step}"),
    ])
    cypher = response.content.strip().replace("```cypher", "").replace("```", "").strip()
    # Fix quoted property names
    cypher = re.sub(r'\.\"([^\"`]+)\"', r'.`\1`', cypher)
    return cypher


def _graph_retrieve(cypher: str) -> list[dict]:
    """Execute Cypher và trả về records từ Neo4j."""
    from backend.app.core.neo4j_client import Neo4jClient
    try:
        return Neo4jClient.execute_query(cypher)
    except Exception as exc:
        return [{"error": str(exc), "query": cypher}]


def _vector_retrieve(step: str, top_k: int) -> list:
    """FAISS vector search — chỉ gọi khi graph kết quả ít."""
    try:
        from pipeline.retrieval.vector_retriever import retrieve_chunks
        return retrieve_chunks(step, top_k=top_k, refresh=True)
    except Exception:
        return []


def retrieve_from_graph(state: AgentState) -> dict:
    """
    Node: Graph-first retrieval theo từng bước trong plan.

    Graph (Neo4j) là PRIMARY retrieval.
    Vector (FAISS) chỉ được gọi khi graph trả về < 3 records.
    """
    from backend.app.core.llm_client import get_llm

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if current_step >= len(plan):
        return {"current_step": current_step}

    step = plan[current_step]
    llm = get_llm()
    top_k = int(state.get("top_k", 5) or 5)

    # ── PRIMARY: Graph retrieval ──────────────────────────────────────────────
    cypher = _generate_cypher(step, llm)
    records = _graph_retrieve(cypher)
    valid_records = [r for r in records if "error" not in r]

    # ── SUPPLEMENTARY: Vector search — chỉ khi graph thiếu kết quả ──────────
    # alpha=0.2: 80% KG weight, 20% vector weight
    vector_results = []
    if len(valid_records) < 3:
        vector_results = _vector_retrieve(step, top_k=top_k)

    # ── Fusion & context building ─────────────────────────────────────────────
    context_text = ""
    try:
        from pipeline.retrieval.fusion import build_llm_context, reciprocal_rank_fusion
        # alpha=0.2 → KG nặng 80%, vector chỉ 20%
        fused = reciprocal_rank_fusion(vector_results, valid_records, alpha=0.2)
        context_text = build_llm_context(fused, query=step, cypher=cypher, max_items=top_k)
    except Exception as exc:
        # Fallback: format KG results thủ công
        if valid_records:
            import json
            context_text = (
                "## Structured Facts (Knowledge Graph — Primary)\n"
                f"Cypher: `{cypher}`\n"
                + "\n".join(
                    f"[{i+1}] {json.dumps(r, ensure_ascii=False, default=str)}"
                    for i, r in enumerate(valid_records[:top_k])
                )
            )
        else:
            context_text = f"*No graph results. Cypher error: {exc}*"

    context = [{
        "step": step,
        "cypher": cypher,
        "kg_results": records,
        "kg_result_count": len(valid_records),
        "vector_results": [c.to_dict() for c in vector_results],
        "vector_used": len(vector_results) > 0,
        "hybrid_context": context_text,
    }]

    return {
        "retrieved_context": state.get("retrieved_context", []) + context,
        "current_step": current_step + 1,
        "needs_more_info": False,
    }
