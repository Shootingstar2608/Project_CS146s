import logging
import json
import asyncio
import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph import run_agent
from agent.nodes.planner import plan_steps
from agent.nodes.retriever import retrieve_from_graph
from agent.nodes.synthesizer import ANSWER_STREAM_PROMPT, build_synthesis_input
from app.models.schemas import ChatRequest, ChatResponse
from app.security.prompt_guard import PromptGuard

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat Endpoint"]
)


def _extract_sources(graph_data: dict) -> list[str]:
    sources_list = []
    if graph_data and isinstance(graph_data, dict):
        nodes = graph_data.get("nodes", [])
        for node in nodes:
            if node.get("type") == "Paper" and node.get("id"):
                sources_list.append(str(node["id"]))
    return list(dict.fromkeys(sources_list))

@router.post("/", response_model=ChatResponse)
async def process_chat(request: ChatRequest) -> Any:
    """
    Endpoint nhận câu hỏi từ người dùng, chạy qua hệ thống Hybrid GraphRAG
    và trả về câu trả lời, nguồn trích dẫn, các bước suy luận và graph data.
    """
    try:
        safe_message = PromptGuard.verify_and_clean(request.message)
        alpha_override = getattr(request, "alpha", None)
        top_k = getattr(request, "top_k", 5)

        result = await run_agent(
            user_query=safe_message, 
            alpha_override=alpha_override, 
            top_k=top_k
        )
        
        graph_data = result.get("graph_data", {})

        return ChatResponse(
            answer=result.get("answer", "Xin lỗi, tôi không thể trả lời câu hỏi này."),
            sources=_extract_sources(graph_data),
            reasoning_steps=result.get("reasoning_steps", []),
            graph_data=graph_data
        )

    except Exception as e:
        logger.error(f"Lỗi trong quá trình xử lý Chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ: {str(e)}")


def _event(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


@router.post("/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    """Stream transparent GraphRAG progress and answer tokens as NDJSON."""
    safe_message = PromptGuard.verify_and_clean(request.message)
    alpha_override = getattr(request, "alpha", None)
    top_k = getattr(request, "top_k", 5)

    def run_agent_stream(emit) -> None:
        state = {
            "messages": [],
            "user_query": safe_message,
            "plan": [],
            "current_step": 0,
            "retrieved_context": [],
            "final_answer": "",
            "graph_data": {"nodes": [], "edges": []},
            "needs_more_info": False,
            "alpha": alpha_override if alpha_override is not None else 0.5,
            "top_k": top_k,
        }
        trace: list[str] = []
        answer_parts: list[str] = []
        graph_data: dict[str, Any] = {"nodes": [], "edges": []}

        try:
            trace.append("Planning retrieval steps.")
            emit("status", {"label": "Planning", "message": "Planning retrieval steps."})
            plan_update = plan_steps(state)
            state.update(plan_update)
            trace.extend([f"Plan: {step}" for step in state.get("plan", [])])
            emit("trace", {"steps": trace})

            while state.get("current_step", 0) < len(state.get("plan", [])):
                step_index = int(state.get("current_step", 0))
                step = state["plan"][step_index]
                emit("status", {"label": "Traversing graph", "message": step})
                before_count = len(state.get("retrieved_context", []))
                retrieve_update = retrieve_from_graph(state)
                state.update(retrieve_update)
                context = state.get("retrieved_context", [])
                latest = context[-1] if len(context) > before_count else {}
                kg_count = len(latest.get("kg_results") or [])
                vector_count = len(latest.get("vector_results") or [])
                trace.append(f"Retrieved {kg_count} graph records and {vector_count} vector chunks for: {step}")
                emit("trace", {"steps": trace})

            emit("status", {"label": "Synthesizing", "message": "Writing the answer from retrieved sources."})
            from backend.app.core.llm_client import get_llm

            llm = get_llm()
            _, human_text = build_synthesis_input(state)
            for chunk in llm.stream([
                SystemMessage(content=ANSWER_STREAM_PROMPT),
                HumanMessage(content=human_text),
            ]):
                token = getattr(chunk, "content", "") or ""
                if token:
                    answer_parts.append(token)
                    emit("token", {"content": token})

            emit("status", {"label": "Citing sources", "message": "Preparing sources and graph trace."})
            try:
                from agent.nodes.synthesizer import synthesize_answer

                structured = synthesize_answer({**state, "final_answer": "".join(answer_parts)})
                graph_data = structured.get("graph_data", {}) or {"nodes": [], "edges": []}
            except Exception:
                graph_data = {"nodes": [], "edges": []}

            sources = _extract_sources(graph_data)
            if not sources:
                # Fall back to vector chunk paper ids/titles when JSON graph output omits Paper nodes.
                for item in state.get("retrieved_context", []):
                    for chunk in item.get("vector_results", []):
                        ref = chunk.get("paper_id") or chunk.get("title")
                        if ref:
                            sources.append(str(ref))
                sources = list(dict.fromkeys(sources))

            trace.append(f"Prepared {len(sources)} cited source reference{'' if len(sources) == 1 else 's'}.")
            emit("sources", {"sources": sources, "graph_data": graph_data, "reasoning_steps": trace})
            emit(
                "final",
                {
                    "answer": "".join(answer_parts),
                    "sources": sources,
                    "reasoning_steps": trace,
                    "graph_data": graph_data,
                },
            )
        except Exception as exc:
            logger.exception("Streaming chat failed")
            emit("error", {"message": str(exc), "reasoning_steps": trace})

    async def generate():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def emit(event_type: str, payload: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, _event(event_type, payload))

        def worker() -> None:
            try:
                run_agent_stream(emit)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(generate(), media_type="application/x-ndjson")
