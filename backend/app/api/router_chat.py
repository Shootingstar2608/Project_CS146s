import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from agent.graph import run_agent
from app.models.schemas import ChatRequest, ChatResponse
from app.security.prompt_guard import PromptGuard

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat Endpoint"]
)

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
        
        # Extract sources from graph data nodes if available
        sources_list = []
        graph_data = result.get("graph_data", {})
        if graph_data and isinstance(graph_data, dict):
            nodes = graph_data.get("nodes", [])
            for node in nodes:
                if node.get("type") == "Paper" and node.get("id"):
                    sources_list.append(str(node["id"]))

        return ChatResponse(
            answer=result.get("answer", "Xin lỗi, tôi không thể trả lời câu hỏi này."),
            sources=sources_list,
            reasoning_steps=result.get("reasoning_steps", []),
            graph_data=graph_data
        )

    except Exception as e:
        logger.error(f"Lỗi trong quá trình xử lý Chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ: {str(e)}")