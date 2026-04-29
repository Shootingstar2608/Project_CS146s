"""
Agent Node: Planner — Phân tích câu hỏi, lập kế hoạch suy luận đa bước.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState

PLANNER_PROMPT = """Bạn là Planning Agent cho hệ thống nghiên cứu khoa học.

Cho câu hỏi của người dùng, hãy lập KẾ HOẠCH gồm các bước cần thực hiện.

Ví dụ: "So sánh Transformer và BERT trên bài toán NER"
Kế hoạch:
1. Tìm thông tin về Transformer trong Knowledge Graph
2. Tìm thông tin về BERT trong Knowledge Graph
3. Tìm các metric liên quan đến NER
4. So sánh và tổng hợp

Trả về kế hoạch, mỗi bước trên 1 dòng bắt đầu bằng số thứ tự."""


def plan_steps(state: AgentState) -> dict:
    """Node: Phân tích câu hỏi → lập kế hoạch multi-step."""
    from backend.app.core.llm_client import get_llm

    llm = get_llm()

    response = llm.invoke([
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=f"Câu hỏi: {state['user_query']}"),
    ])

    # Parse kế hoạch
    steps = [
        line.strip().lstrip("0123456789.)").strip()
        for line in response.content.split("\n")
        if line.strip() and len(line.strip()) > 3 and line.strip()[0].isdigit()
    ]

    if not steps:
        steps = [f"Tìm kiếm thông tin liên quan đến: {state['user_query']}"]

    return {
        "plan": steps,
        "current_step": 0,
        "messages": state.get("messages", []) + [response],
    }
