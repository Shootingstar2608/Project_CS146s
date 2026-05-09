"""
Agent Node: Planner — Phân tích câu hỏi, lập kế hoạch suy luận đa bước.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from agent.state import AgentState  # fix: absolute import từ project root

PLANNER_PROMPT = """Bạn là Planning Agent cho hệ thống nghiên cứu khoa học dựa trên Knowledge Graph.

Cho câu hỏi của người dùng, hãy lập KẾ HOẠCH gồm các bước query Knowledge Graph cần thực hiện.
Mỗi bước phải là 1 hành động truy vấn cụ thể, KHÔNG phải bước tổng hợp.

Ví dụ: "So sánh Transformer và BERT trên bài toán NER"
Kế hoạch:
1. Tìm thông tin về Methodology: Transformer trong Knowledge Graph
2. Tìm thông tin về Methodology: BERT trong Knowledge Graph
3. Tìm các Result (metric) liên quan đến Task: NER
4. Tìm các Paper dùng cả Transformer lẫn BERT

LUẬT:
- Tối đa 5 bước
- Mỗi bước phải rõ loại entity cần tìm (Methodology / Paper / Dataset / Result...)
- Không có bước "tổng hợp" hay "so sánh" — đó là việc của Synthesizer
- Trả về ĐÚNG format: mỗi bước trên 1 dòng, bắt đầu bằng số thứ tự"""


def plan_steps(state: AgentState) -> dict:
    """Node: Phân tích câu hỏi → lập kế hoạch multi-step."""
    from backend.app.core.llm_client import get_llm

    llm = get_llm()

    response = llm.invoke([
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=f"Câu hỏi: {state['user_query']}"),
    ])

    # Parse kế hoạch từ response
    steps = [
        line.strip().lstrip("0123456789.)").strip()
        for line in response.content.split("\n")
        if line.strip() and len(line.strip()) > 3 and line.strip()[0].isdigit()
    ]

    # Fallback nếu LLM không trả đúng format
    if not steps:
        steps = [f"Tìm kiếm thông tin liên quan đến: {state['user_query']}"]

    # Guard: giới hạn tối đa 5 bước tránh vòng lặp vô tận
    steps = steps[:5]

    return {
        "plan": steps,
        "current_step": 0,
        "messages": state.get("messages", []) + [response],
    }