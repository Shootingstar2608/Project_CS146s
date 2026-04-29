"""
Pipeline: Entity Extractor — Gọi LLM trích xuất Entities & Relations.

Sử dụng `instructor` + Pydantic để ép LLM trả JSON chuẩn.
"""

import instructor
from pipeline.extraction.schemas import ExtractionResult, PaperMetadata
from pipeline.extraction.prompts import EXTRACTION_PROMPT, METADATA_PROMPT


def extract_entities_from_text(
    text: str,
    section_heading: str = "",
    llm=None,
) -> ExtractionResult:
    """
    Trích xuất entities và relations từ 1 đoạn text bằng LLM.
    """
    if llm is None:
        from backend.app.core.llm_client import get_llm
        llm = get_llm()

    client = instructor.from_langchain(llm)

    result = client.chat.completions.create(
        response_model=ExtractionResult,
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": f"Section: {section_heading}\n\n{text}"},
        ],
    )

    return result


def extract_paper_metadata(text: str, llm=None) -> PaperMetadata:
    """
    Trích xuất metadata từ phần đầu paper.
    """
    if llm is None:
        from backend.app.core.llm_client import get_llm
        llm = get_llm()

    client = instructor.from_langchain(llm)

    result = client.chat.completions.create(
        response_model=PaperMetadata,
        messages=[
            {"role": "system", "content": METADATA_PROMPT},
            {"role": "user", "content": text[:2000]},
        ],
    )

    return result
