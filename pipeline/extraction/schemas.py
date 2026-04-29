"""
Pydantic schemas dùng với `instructor` để ép LLM trả JSON chuẩn
cho Entity & Relation extraction.

KHÔNG SỬ DỤNG chunking văn bản thuần túy — theo yêu cầu đề tài.
"""

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Một thực thể trích xuất từ bài báo."""
    name: str = Field(..., description="Tên thực thể, VD: 'GPT-4', 'Vaswani et al.'")
    type: str = Field(..., description="Loại: Paper | Author | Method | Metric | Dataset | Task | Organization")
    description: str = Field(default="", description="Mô tả ngắn trong ngữ cảnh bài báo")


class Relation(BaseModel):
    """Mối quan hệ giữa 2 thực thể."""
    source: str = Field(..., description="Tên Entity nguồn")
    target: str = Field(..., description="Tên Entity đích")
    relation: str = Field(..., description="CITES | USES_METHOD | ACHIEVES_METRIC | AUTHORED_BY | EVALUATED_ON | BELONGS_TO | IMPROVES | COMPARED_WITH")
    evidence: str = Field(default="", description="Trích dẫn câu gốc làm bằng chứng")


class ExtractionResult(BaseModel):
    """Kết quả trích xuất từ 1 đoạn text."""
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


class PaperMetadata(BaseModel):
    """Metadata tổng quan bài báo."""
    title: str = Field(..., description="Tên bài báo")
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None)
    abstract: str = Field(default="")
    keywords: list[str] = Field(default_factory=list)
