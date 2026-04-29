"""
Pipeline: PDF Parser — Parse tài liệu khoa học PDF 2 cột, bảng biểu.

Sử dụng PyMuPDF (fitz). sort=True để đọc đúng thứ tự 2 cột.
"""

import fitz  # PyMuPDF
import re


def parse_pdf(file_path: str) -> dict:
    """
    Parse file PDF → text sạch.

    Returns:
        {
            "full_text": str,
            "pages": [{"page_num": int, "text": str}, ...],
            "metadata": {"title": str, "author": str, ...},
            "num_pages": int,
        }
    """
    doc = fitz.open(file_path)
    pages = []
    full_text_parts = []

    for page_num, page in enumerate(doc, start=1):
        # sort=True xử lý layout 2 cột theo đúng thứ tự đọc
        text = page.get_text("text", sort=True)
        text = _clean_page_text(text)
        pages.append({"page_num": page_num, "text": text})
        full_text_parts.append(text)

    metadata = doc.metadata or {}
    num_pages = len(doc)
    doc.close()

    full_text = "\n\n".join(full_text_parts)
    full_text = _normalize_text(full_text)

    return {
        "full_text": full_text,
        "pages": pages,
        "metadata": {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
        },
        "num_pages": num_pages,
    }


def _clean_page_text(text: str) -> str:
    """Loại bỏ noise từ mỗi trang."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Bỏ số trang đứng riêng
        if stripped.isdigit() and len(stripped) <= 4:
            continue
        # Bỏ dòng quá ngắn
        if len(stripped) < 3:
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def _normalize_text(text: str) -> str:
    """Chuẩn hóa text sau khi ghép các trang."""
    import unicodedata
    text = unicodedata.normalize("NFKC", text)
    # Fix word bị ngắt dòng: "trans-\nformer" → "transformer"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Collapse nhiều dòng trống
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_sections(text: str) -> list[dict]:
    """
    Chia text thành sections dựa trên heading (VD: "1. Introduction").

    Returns: [{"heading": str, "content": str}, ...]
    """
    # Pattern heading phổ biến: "1. Introduction", "2.1 Method", "Abstract"
    pattern = r"(?:^|\n)((?:\d+\.?\d*\.?\s+)?[A-Z][A-Za-z\s]{2,50})\n"
    parts = re.split(pattern, text)

    sections = []
    if parts[0].strip():
        sections.append({"heading": "Header/Abstract", "content": parts[0].strip()})

    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if content:
            sections.append({"heading": heading, "content": content})

    # Nếu không tách được sections, trả về toàn bộ text như 1 section
    if not sections:
        sections = [{"heading": "Full Document", "content": text}]

    return sections
