"""
Pydantic schemas — Request / Response models cho API.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ════════════════════════════════════════
#  Upload
# ════════════════════════════════════════
class UploadResponse(BaseModel):
    document_id: str = Field(..., description="UUID của tài liệu vừa upload")
    filename: str
    status: str = Field(default="processing", description="processing | completed | failed")
    message: str = Field(default="File đã được tiếp nhận và đang xử lý ngầm.")


# ════════════════════════════════════════
#  Chat
# ════════════════════════════════════════
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Câu hỏi của người dùng")
    session_id: str | None = Field(default=None, description="ID phiên chat (tự tạo nếu None)")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Câu trả lời từ Agent")
    sources: list[str] = Field(default_factory=list, description="Danh sách paper sources")
    reasoning_steps: list[str] = Field(
        default_factory=list,
        description="Các bước suy luận Agent đã thực hiện (Explainable AI)",
    )
    graph_data: "GraphData | None" = Field(
        default=None,
        description="Dữ liệu graph liên quan để Frontend hiển thị visualization",
    )


# ════════════════════════════════════════
#  Graph Visualization
# ════════════════════════════════════════
class GraphNode(BaseModel):
    id: str
    label: str
    type: str = Field(..., description="Paper | Author | Method | Metric | Dataset")
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = Field(..., description="CITES | USES_METHOD | ACHIEVES | AUTHORED_BY | ...")
    properties: dict = Field(default_factory=dict)


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ════════════════════════════════════════
#  Document (danh sách papers đã upload)
# ════════════════════════════════════════
class DocumentInfo(BaseModel):
    id: str
    filename: str
    status: str
    uploaded_at: datetime
    entity_count: int = 0
    relation_count: int = 0


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo] = Field(default_factory=list)
    total: int = 0
