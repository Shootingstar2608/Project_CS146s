"""
Pydantic schemas — Cấu trúc dữ liệu cho Entity/Relation extraction.

Sử dụng với `instructor` để ép LLM trả JSON chuẩn.
Đã cập nhật theo schema_sample.md: 9 Node types, UUID IDs, aliases, edge properties.
"""

from pydantic import BaseModel, Field
from uuid import uuid4
from enum import Enum


# ══════════════════════════════════════════════════════════════
# ENUM: Liệt kê cứng các loại Entity và Relation
# ══════════════════════════════════════════════════════════════

class PaperCategory(str, Enum):
    ML_AI = "ML/AI"
    IOT_HARDWARE = "IoT/Hardware"
    NETWORKS = "Networks"
    THEORY = "Theory"
    SURVEYS = "Surveys"
    UNCATEGORIZED = "Uncategorized"


class EntityType(str, Enum):
    PAPER = "Paper"
    AUTHOR = "Author"
    ORGANIZATION = "Organization"
    CONFERENCE = "Conference"
    TOPIC = "Topic"           # Lĩnh vực rộng: "NLP", "Computer Vision"
    TASK = "Task"             # Bài toán cụ thể: "Machine Translation", "NER", "Image Classification"
    METHODOLOGY = "Methodology"
    DATASET = "Dataset"
    RESULT = "Result"


class RelationType(str, Enum):
    AUTHORED = "AUTHORED"                   # Author → Paper
    AFFILIATED_WITH = "AFFILIATED_WITH"     # Author → Organization
    PUBLISHED_AT = "PUBLISHED_AT"           # Paper → Conference
    COVERS_TOPIC = "COVERS_TOPIC"           # Paper → Topic
    ADDRESSES_TASK = "ADDRESSES_TASK"       # Paper → Task (bài toán paper giải quyết)
    USES_METHOD = "USES_METHOD"             # Paper → Methodology
    EVALUATED_ON = "EVALUATED_ON"           # Paper → Dataset
    CITES = "CITES"                         # Paper → Paper
    ACHIEVES = "ACHIEVES"                   # Paper → Result
    SUBTOPIC_OF = "SUBTOPIC_OF"             # Topic → Topic
    VARIANT_OF = "VARIANT_OF"               # Methodology → Methodology (biến thể)
    IMPROVES = "IMPROVES"                   # Methodology → Methodology (cải tiến từ)
    COMPARED_WITH = "COMPARED_WITH"         # Methodology → Methodology (so sánh baseline)
    RESULT_ON = "RESULT_ON"                 # Result → Dataset
    RESULT_WITH = "RESULT_WITH"             # Result → Methodology


# ══════════════════════════════════════════════════════════════
# ENTITY SCHEMAS
# ══════════════════════════════════════════════════════════════

class Entity(BaseModel):
    """Một thực thể trích xuất từ bài báo."""
    entity_id: str = Field(default_factory=lambda: str(uuid4()), description="UUID tự sinh")
    name: str = Field(..., description="Tên canonical, VD: 'GPT-4', 'Vaswani et al.'")
    type: EntityType = Field(..., description="Loại entity")
    aliases: list[str] = Field(default_factory=list, description="Các tên gọi khác (VD: ['GPT-4 model', 'OpenAI GPT-4'])")
    description: str = Field(default="", description="Mô tả ngắn trong ngữ cảnh bài báo")


class ResultEntity(BaseModel):
    """Kết quả metric cụ thể — tách riêng vì có thêm value/unit."""
    entity_id: str = Field(default_factory=lambda: str(uuid4()))
    metric_name: str = Field(..., description="Tên metric: 'Accuracy', 'F1-Score', 'BLEU'...")
    value: float = Field(..., description="Giá trị đạt được")
    unit: str = Field(default="%", description="Đơn vị: '%', 'ms'...")
    context: str = Field(default="", description="Bối cảnh: 'on ImageNet validation set'")
    is_sota: bool = Field(default=False, description="Có phải SOTA tại thời điểm publish không")


# ══════════════════════════════════════════════════════════════
# RELATION SCHEMAS
# ══════════════════════════════════════════════════════════════

class Relation(BaseModel):
    """Mối quan hệ giữa 2 thực thể."""
    source: str = Field(..., description="Tên Entity nguồn")
    target: str = Field(..., description="Tên Entity đích")
    relation: RelationType = Field(..., description="Loại quan hệ")
    evidence: str = Field(default="", description="Trích dẫn câu gốc làm bằng chứng")
    # Edge properties
    properties: dict = Field(default_factory=dict, description="Thuộc tính bổ sung trên edge (VD: role, relevance)")


# ══════════════════════════════════════════════════════════════
# EXTRACTION RESULT (output chính từ LLM)
# ══════════════════════════════════════════════════════════════

class ExtractionResult(BaseModel):
    """Kết quả trích xuất từ 1 đoạn text."""
    entities: list[Entity] = Field(default_factory=list, description="Danh sách thực thể")
    results: list[ResultEntity] = Field(default_factory=list, description="Kết quả metric")
    relations: list[Relation] = Field(default_factory=list, description="Danh sách quan hệ")


# ══════════════════════════════════════════════════════════════
# PAPER METADATA (chỉ trích 1 lần từ header paper)
# ══════════════════════════════════════════════════════════════

class PaperMetadata(BaseModel):
    """Metadata tổng quan bài báo — trích từ phần đầu."""
    paper_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., description="Tên bài báo")
    categories: list[PaperCategory] = Field(default_factory=lambda: [PaperCategory.UNCATEGORIZED], description="Danh sách các danh mục phù hợp (chọn 1-2 cái): ML/AI, IoT/Hardware, Networks, Theory, Surveys. Trả về [Uncategorized] nếu không chắc chắn.")
    authors: list[str] = Field(default_factory=list, description="Danh sách tác giả")
    year: int | None = Field(default=None, description="Năm xuất bản")
    abstract: str = Field(default="", description="Tóm tắt")
    keywords: list[str] = Field(default_factory=list, description="Từ khóa")
    venue: str = Field(default="", description="Hội nghị/tạp chí (VD: 'NeurIPS 2024')")
    doi: str = Field(default="", description="DOI nếu có")


# ══════════════════════════════════════════════════════════════
# ENTITY RESOLUTION
# ══════════════════════════════════════════════════════════════

class ResolutionCandidate(BaseModel):
    """Cặp entity nghi ngờ trùng lặp — cần LLM xác nhận."""
    entity_a: str = Field(..., description="Tên entity thứ nhất")
    entity_b: str = Field(..., description="Tên entity thứ hai")
    entity_type: EntityType | None = Field(default=None, description="Loại entity")
    similarity_score: float = Field(default=0.0, description="Điểm similarity (0-1)")
    is_same: bool = Field(default=False, description="LLM phán quyết: có phải cùng 1 entity không")
    reasoning: str = Field(default="", description="Lý do")
