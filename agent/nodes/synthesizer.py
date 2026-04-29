"""
Agent Node: Synthesizer — Tổng hợp context thành câu trả lời cuối cùng.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState

SYNTHESIS_PROMPT = """Bạn là trợ lý nghiên cứu khoa học.

Dựa trên thông tin từ Knowledge Graph bên dưới, hãy trả lời câu hỏi:
- Trả lời bằng tiếng Việt
- Chỉ dùng thông tin từ context, KHÔNG bịa
- Nếu thiếu thông tin, nói rõ
- Trích dẫn tên paper
- Dùng markdown"""


def synthesize_answer(state: AgentState) -> dict:
    """Node: Tổng hợp context → câu trả lời."""
    from backend.app.core.llm_client import get_llm

    llm = get_llm()
    context = state.get("retrieved_context", [])
    plan = state.get("plan", [])
    context_text = json.dumps(context, ensure_ascii=False, indent=2, default=str)

    response = llm.invoke([
        SystemMessage(content=SYNTHESIS_PROMPT),
        HumanMessage(content=(
            f"Câu hỏi: {state['user_query']}\n\n"
            f"Kế hoạch:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan))
            + f"\n\nContext:\n{context_text}"
        )),
    ])

    return {
        "final_answer": response.content,
        "messages": state.get("messages", []) + [response],
    }
