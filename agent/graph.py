"""
Agent Graph — LangGraph StateGraph definition.

Flow: Plan → Retrieve (loop) → Synthesize → END

Extended to:
  - Accept alpha_override for per-query hybrid weight
  - Return vector_chunks and retrieval_mode in result
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.planner import plan_steps
from agent.nodes.retriever import retrieve_from_graph
from agent.nodes.synthesizer import synthesize_answer


def should_continue(state: AgentState) -> str:
    """Router: more steps in plan → retrieve again, else synthesize."""
    current = state.get("current_step", 0)
    plan = state.get("plan", [])
    return "retrieve" if current < len(plan) else "synthesize"


def build_agent_graph():
    """
    Build and compile the LangGraph agent:

        Plan → Retrieve ← (loop) → Synthesize → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("plan", plan_steps)
    graph.add_node("retrieve", retrieve_from_graph)
    graph.add_node("synthesize", synthesize_answer)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        should_continue,
        {"retrieve": "retrieve", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)

    return graph.compile()


# Compiled once at module import
agent_executor = build_agent_graph()


async def run_agent(
    user_query: str,
    alpha_override: float | None = None,
    top_k: int = 5,
) -> dict:
    """
    Entry point: run the hybrid agent for one question.

    Args:
        user_query:     Natural-language question.
        alpha_override: Optional fusion weight (0=KG, 1=vector).
        top_k:          Vector retrieval candidate count.

    Returns:
        {
            "answer":           str,
            "reasoning_steps":  list[str],
            "retrieved_chunks": list[dict],
            "graph_data":       dict,
            "retrieval_mode":   str,
            "alpha_used":       float,
        }
    """
    initial_state = {
        "messages": [],
        "user_query": user_query,
        "plan": [],
        "current_step": 0,
        "retrieved_context": [],
        "vector_chunks": [],
        "final_answer": "",
        "graph_data": {"nodes": [], "edges": []},
        "needs_more_info": False,
        "retrieval_mode": "hybrid",
        "alpha": 0.5,
        "alpha_override": alpha_override,
    }

    result = await agent_executor.ainvoke(initial_state)

    return {
        "answer": result.get("final_answer", ""),
        "reasoning_steps": result.get("plan", []),
        "retrieved_chunks": result.get("vector_chunks", []),
        "graph_data": result.get("graph_data", {}),
        "retrieval_mode": result.get("retrieval_mode", "hybrid"),
        "alpha_used": result.get("alpha", 0.5),
    }
