"""
Agent State — Shared state across all LangGraph nodes.

Extended with hybrid retrieval fields:
  - vector_chunks:    raw vector-retrieved chunks (for citations)
  - retrieval_mode:   "kg" | "vector" | "hybrid"
  - alpha:            fusion weight actually used
  - alpha_override:   optional per-request override from API caller
"""

from typing import Annotated, List
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State shared across all LangGraph nodes."""

    # Accumulated messages (LangGraph merge)
    messages: Annotated[list, add_messages]

    # Original user question
    user_query: str

    # Multi-step plan from Planner
    plan: List[str]

    # Current plan step index
    current_step: int

    # KG facts accumulated across retrieval steps
    retrieved_context: List[dict]

    # NEW: Semantic chunks from vector retrieval
    vector_chunks: List[dict]

    # Final synthesized answer
    final_answer: str

    # Graph data for frontend visualization
    graph_data: dict

    # Whether more info is needed (legacy flag, kept for compatibility)
    needs_more_info: bool

    # NEW: Retrieval mode used ("kg" | "vector" | "hybrid")
    retrieval_mode: str

    # NEW: Fusion alpha weight used in this run
    alpha: float

    # NEW: Optional per-query alpha override from API caller (None = use router)
    alpha_override: float | None
