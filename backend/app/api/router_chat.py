import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any

from app.models.schemas import ChatRequest, ChatResponse
from app.security.prompt_guard import PromptGuard


from agent.graph import run_agent

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
        
        # 3. Trích xuất và định dạng dữ liệu đầu ra cho khớp với Schema ChatResponse
        raw_chunks = result.get("retrieved_chunks", [])
        sources_list = []
        
        for chunk in raw_chunks:
            metadata = chunk.get("metadata", {})
            source_info = metadata.get("source") or chunk.get("source") or chunk.get("filename")
            
            if source_info and source_info not in sources_list:
                sources_list.append(str(source_info))

        return ChatResponse(
            answer=result.get("answer", "Xin lỗi, tôi trả lời."),
            sources=sources_list,
            reasoning_steps=result.get("reasoning_steps", []),
            graph_data=result.get("graph_data", None)
        )

    except Exception as e:
        logger.error(f"Lỗi trong quá trình xử lý Chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi máy chủ nội bộ: {str(e)}")