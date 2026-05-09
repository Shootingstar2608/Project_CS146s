"""
Agent Node: Synthesizer — Tổng hợp context thành câu trả lời cuối cùng chuẩn JSON.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState  # fix: absolute import từ project root

SYNTHESIS_PROMPT = """Bạn là trợ lý nghiên cứu khoa học cốt lõi của hệ thống GraphRAG.

Dựa trên thông tin từ Knowledge Graph và Kế hoạch bên dưới, hãy trả lời câu hỏi của người dùng.

LUẬT QUAN TRỌNG:
1. Trả lời bằng tiếng Việt, dùng Markdown để format (## Heading, * List, **bold**).
2. Chỉ dùng thông tin từ Context được cung cấp, KHÔNG bịa đặt.
   Nếu thiếu thông tin, nói rõ: "Tài liệu không đề cập đến...".
3. Trích dẫn tên paper hoặc entity cụ thể từ graph nếu có.
4. Phần graph_data: liệt kê các entity và quan hệ đã THỰC SỰ dùng để trả lời.

BẮT BUỘC trả về ĐÚNG định dạng JSON sau (không bọc trong markdown code block):
{
    "answer": "Câu trả lời chi tiết bằng Markdown...",
    "sources": ["Tên paper 1", "Tên paper 2"],
    "graph_data": {
        "nodes": [
            {"id": "Transformer", "type": "Methodology"},
            {"id": "BERT", "type": "Methodology"}
        ],
        "edges": [
            {"source": "Paper A", "target": "Transformer", "relation": "USES_METHOD"}
        ]
    }
}"""


def synthesize_answer(state: AgentState) -> dict:
    """Node: Tổng hợp context → câu trả lời + graph_data để visualize."""
    from backend.app.core.llm_client import get_llm

    llm = get_llm().bind(response_format={"type": "json_object"})

    context = state.get("retrieved_context", [])
    plan = state.get("plan", [])
    context_text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    plan_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan))

    response = llm.invoke([
        SystemMessage(content=SYNTHESIS_PROMPT),
        HumanMessage(content=(
            f"Câu hỏi: {state['user_query']}\n\n"
            f"Kế hoạch đã thực hiện:\n{plan_text}\n\n"
            f"Context thu thập được từ Knowledge Graph:\n{context_text}"
        )),
    ])

    # Parse JSON response với fallback an toàn
    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError:
        parsed = {
            "answer": response.content,
            "sources": [],
            "graph_data": {"nodes": [], "edges": []},
        }

    # Validate và normalize graph_data
    graph_data = parsed.get("graph_data", {})
    if not isinstance(graph_data.get("nodes"), list):
        graph_data["nodes"] = []
    if not isinstance(graph_data.get("edges"), list):
        graph_data["edges"] = []    
    # Normalize nodes: ensure `type` field exists
    for node in graph_data["nodes"]:
        if "type" not in node and "kind" in node:
            node["type"] = node["kind"]
        if "type" not in node:
            node["type"] = "Entity"
    
    # Normalize edges: ensure `relation` field exists
    for edge in graph_data["edges"]:
        if "relation" not in edge and "label" in edge:
            edge["relation"] = edge["label"]
        if "relation" not in edge:
            edge["relation"] = "RELATED_TO"
    return {
        # final_answer là str để đồng bộ với AgentState
        "final_answer": parsed.get("answer", ""),
        # graph_data lưu riêng để frontend visualize
        "graph_data": graph_data,
        "messages": state.get("messages", []) + [response],
    }