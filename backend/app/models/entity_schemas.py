"""
Pydantic schemas dùng với thư viện `instructor` để ép LLM
trả về Entities & Relations ở dạng JSON chuẩn.

Minh Khánh (Data Engineer) sẽ import các schema này trong pipeline/extraction/.
"""

from pydantic import BaseModel, Field


# ════════════════════════════════════════
#  Entity Definitions
# ════════════════════════════════════════
class Entity(BaseModel):
    """Một thực thể được trích xuất từ bài báo khoa học."""

    name: str = Field(..., description="Tên thực thể, ví dụ: 'GPT-4', 'Vaswani et al.'")
    type: str = Field(
        ...,
        description="Loại thực thể: Paper | Author | Method | Metric | Dataset | Task | Organization",
    )
    description: str = Field(
        default="",
        description="Mô tả ngắn gọn về thực thể này trong ngữ cảnh bài báo",
    )


class Relation(BaseModel):
    """Một mối quan hệ giữa 2 thực thể."""

    source: str = Field(..., description="Tên Entity nguồn")
    target: str = Field(..., description="Tên Entity đích")
    relation: str = Field(
        ...,
        description=(
            "Loại quan hệ: CITES | USES_METHOD | ACHIEVES_METRIC | "
            "AUTHORED_BY | EVALUATED_ON | BELONGS_TO | IMPROVES | COMPARED_WITH"
        ),
    )
    evidence: str = Field(
        default="",
        description="Trích dẫn câu văn gốc trong paper làm bằng chứng",
    )


# ════════════════════════════════════════
#  Extraction Result (LLM trả về cái này)
# ════════════════════════════════════════
class ExtractionResult(BaseModel):
    """Kết quả trích xuất từ 1 đoạn văn bản (hoặc 1 section) của paper."""

    entities: list[Entity] = Field(
        default_factory=list,
        description="Danh sách tất cả thực thể được tìm thấy",
    )
    relations: list[Relation] = Field(
        default_factory=list,
        description="Danh sách tất cả mối quan hệ giữa các thực thể",
    )


class PaperMetadata(BaseModel):
    """Metadata cấp cao của bài báo — trích xuất 1 lần duy nhất."""

    title: str = Field(..., description="Tên bài báo")
    authors: list[str] = Field(default_factory=list, description="Danh sách tác giả")
    year: int | None = Field(default=None, description="Năm xuất bản")
    abstract: str = Field(default="", description="Tóm tắt bài báo")
    keywords: list[str] = Field(default_factory=list, description="Từ khóa")


# ════════════════════════════════════════
#  Entity Resolution
# ════════════════════════════════════════
class ResolutionCandidate(BaseModel):
    """Cặp entity có khả năng trùng lặp."""

    entity_a: str
    entity_b: str
    similarity_score: float = Field(..., ge=0, le=1)
    is_same: bool = Field(..., description="LLM xác nhận có phải cùng 1 thực thể không")
    reasoning: str = Field(default="", description="Giải thích lý do merge/không merge")
