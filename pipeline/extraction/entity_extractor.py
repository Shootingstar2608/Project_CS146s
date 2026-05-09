"""
Pipeline: Entity Extractor — Gọi LLM trích xuất Entities & Relations.

Sử dụng `instructor` + Pydantic để ép LLM trả JSON chuẩn.
Đã cập nhật cho schema mới (9 node types, UUID, aliases, Result).
"""

import json
import logging
import re
from langchain_core.messages import SystemMessage, HumanMessage
from pipeline.extraction.schemas import (
    ExtractionResult,
    PaperMetadata,
    ResolutionCandidate,
)
from pipeline.extraction.prompts import EXTRACTION_PROMPT, METADATA_PROMPT, RESOLUTION_PROMPT

logger = logging.getLogger(__name__)


def _extract_json_payload(raw_text: str) -> dict:
    """Extract a JSON object from an LLM response that may include code fences."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")

    return json.loads(text[start : end + 1])

def extract_entities_from_text(
    text: str,
    section_heading: str = "",
    llm=None,
) -> ExtractionResult:
    """
    Trích xuất entities, results, và relations từ 1 đoạn text bằng LLM.
    """
    if llm is None:
        from backend.app.core.llm_client import get_llm
        llm = get_llm()

    structured_llm = llm.with_structured_output(ExtractionResult)
    try:
        result = structured_llm.invoke([
            SystemMessage(content=EXTRACTION_PROMPT),
            HumanMessage(content=f"Section: {section_heading}\n\n{text}"),
        ])
        return result
    except Exception as e:
        logger.error(f"Error in extract_entities_from_text: {e}")
        return ExtractionResult(entities=[], relations=[], results=[])


def extract_paper_metadata(text: str, llm=None) -> PaperMetadata:
    """
    Trích xuất metadata từ phần đầu paper (chỉ chạy 1 lần).
    Lấy ~2000 ký tự đầu (title, authors, abstract area).
    """
    if llm is None:
        from backend.app.core.llm_client import get_llm
        llm = get_llm()

    try:
        response = llm.invoke([
            SystemMessage(content=METADATA_PROMPT),
            HumanMessage(content=text[:2000]),
        ])
        raw = response.content.strip()
        data = _extract_json_payload(raw)
        return PaperMetadata.model_validate(data)
    except Exception as e:
        logger.error(f"Error in extract_paper_metadata: {e}")
        return PaperMetadata(title="Unknown", authors=[], abstract="")


def verify_entity_resolution(
    entity_a: str,
    entity_b: str,
    type_a: str = "Unknown",
    type_b: str = "Unknown",
    score: float = 0.0,
    llm=None,
) -> ResolutionCandidate:
    """
    Dùng LLM xác nhận 2 entity có phải cùng 1 thứ không.
    """
    if llm is None:
        from backend.app.core.llm_client import get_llm
        llm = get_llm()

    prompt = RESOLUTION_PROMPT.format(
        entity_a=entity_a,
        entity_b=entity_b,
        type_a=type_a,
        type_b=type_b,
        score=score,
    )

    structured_llm = llm.with_structured_output(ResolutionCandidate)
    try:
        result = structured_llm.invoke([
            SystemMessage(content="Bạn là Entity Resolution Expert."),
            HumanMessage(content=prompt),
        ])
        result.entity_a = entity_a
        result.entity_b = entity_b
        result.similarity_score = score
        return result
    except Exception as e:
        logger.error(f"Error in verify_entity_resolution: {e}")
        return ResolutionCandidate(entity_a=entity_a, entity_b=entity_b, similarity_score=score, is_same_entity=False, confidence=0.0, reasoning=str(e))
