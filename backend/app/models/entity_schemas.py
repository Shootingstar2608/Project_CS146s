"""
Backend Entity Schemas — Re-export từ pipeline/extraction/schemas.py

Đảm bảo backend và pipeline dùng CÙNG MỘT bộ schema duy nhất.
Import tất cả từ pipeline để tránh duplicate code.

Minh Khánh (Data Engineer) và Tiểu My (Backend) đều import từ đây hoặc từ pipeline.
"""

# Re-export tất cả từ pipeline (single source of truth)
from pipeline.extraction.schemas import (
    EntityType,
    RelationType,
    Entity,
    ResultEntity,
    Relation,
    ExtractionResult,
    PaperMetadata,
    ResolutionCandidate,
)

__all__ = [
    "EntityType",
    "RelationType",
    "Entity",
    "ResultEntity",
    "Relation",
    "ExtractionResult",
    "PaperMetadata",
    "ResolutionCandidate",
]
