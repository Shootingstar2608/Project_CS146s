"""
Agent Node: Retriever — Query Neo4j Knowledge Graph lấy context.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState

CYPHER_PROMPT = """Bạn là chuyên gia Neo4j Cypher.

Graph Schema:
- Node types: Paper, Author, Method, Metric, Dataset, Task, Organization
- Edge types: CITES, USES_METHOD, ACHIEVES_METRIC, AUTHORED_BY, EVALUATED_ON, BELONGS_TO, IMPROVES, COMPARED_WITH
- Mỗi node có property: name, description

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

    response = llm.invoke([
        SystemMessage(content=CYPHER_PROMPT),
        HumanMessage(content=f"Bước tìm kiếm: {step}"),
    ])

    cypher = response.content.strip().replace("```cypher", "").replace("```", "").strip()

    context = []
    try:
        records = Neo4jClient.execute_query(cypher)
        context = records
    except Exception as e:
        context = [{"error": str(e), "query": cypher}]

    return {
        "retrieved_context": state.get("retrieved_context", []) + context,
        "current_step": current_step + 1,
        "needs_more_info": False,
    }
