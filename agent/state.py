"""
Agent State — Định nghĩa trạng thái chia sẻ giữa các node trong LangGraph.
"""

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State chạy xuyên suốt LangGraph graph."""

    # Tin nhắn tích lũy (LangGraph tự merge nhờ add_messages)
    messages: Annotated[list, add_messages]

    # Câu hỏi gốc từ user
    user_query: str

    # Kế hoạch suy luận do Planner tạo
    plan: list[str]

    # Bước hiện tại trong plan
    current_step: int

    # Context thu thập từ Graph
    retrieved_context: list[dict]

    # Câu trả lời cuối cùng
    final_answer: str

    # Dữ liệu graph cho visualization
    graph_data: dict

    # Cờ: cần tìm thêm info không
    needs_more_info: bool
