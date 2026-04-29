"""
Agent Graph — LangGraph StateGraph definition.

Luồng: Plan → Retrieve (loop) → Synthesize → END
"""

import sys
import os

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

    graph.add_node("plan", plan_steps)
    graph.add_node("retrieve", retrieve_from_graph)
    graph.add_node("synthesize", synthesize_answer)

    graph.set_entry_point("plan")

    # Sau plan → đi retrieve bước đầu tiên
    graph.add_edge("plan", "retrieve")

    # Sau retrieve → kiểm tra còn bước nào trong plan không
    graph.add_conditional_edges("retrieve", should_continue, {
        "retrieve": "retrieve",
        "synthesize": "synthesize",
    })

    graph.add_edge("synthesize", END)

    return graph.compile()


# Compile graph 1 lần duy nhất
agent_executor = build_agent_graph()


async def run_agent(user_query: str) -> dict:
    """Entry point: chạy Agent cho 1 câu hỏi."""
    initial_state = {
        "messages": [],
        "user_query": user_query,
        "plan": [],
        "current_step": 0,
        "retrieved_context": [],
        "final_answer": "",
        "graph_data": {"nodes": [], "edges": []},
        "needs_more_info": False,
    }

    result = await agent_executor.ainvoke(initial_state)

    return {
        "answer": result.get("final_answer", ""),
        "reasoning_steps": result.get("plan", []),
        "graph_data": result.get("graph_data", {}),
    }
