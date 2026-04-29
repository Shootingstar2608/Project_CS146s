"""
Pipeline: Image Extractor — Trích xuất và xử lý ảnh từ PDF.

Quy trình:
1. PyMuPDF trích ảnh embedded trong PDF
2. Tìm caption text gần vị trí ảnh ("Figure 1: ...")
3. (Optional) Gửi ảnh cho Vision LLM mô tả nội dung
4. Kết quả text mô tả ảnh → gộp vào pipeline extraction như text thường
"""

import os
import re
import fitz  # PyMuPDF
import base64


def extract_images_from_pdf(file_path: str, output_dir: str = None) -> list[dict]:
    """
    Trích xuất tất cả ảnh từ PDF.

    Returns: [
        {
            "page_num": 1,
            "image_index": 0,
            "image_path": "/path/to/img_p1_0.png",  (nếu output_dir được chỉ định)
            "image_bytes": b"...",
            "width": 800,
            "height": 600,
            "caption": "Figure 1: Architecture of Transformer model",
            "description": ""  (sẽ được Vision LLM điền)
        }
    ]
    """
    doc = fitz.open(file_path)
    results = []

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    for page_num, page in enumerate(doc, start=1):
        # Lấy toàn bộ text của trang để tìm caption
        page_text = page.get_text("text", sort=True)

        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            try:
                # Trích ảnh ra bytes
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]  # png, jpeg, etc.
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                # Bỏ qua ảnh quá nhỏ (icon, bullet, decorative)
                if width < 100 or height < 100:
                    continue

                # Lưu ảnh ra file nếu cần
                image_path = None
                if output_dir:
                    image_path = os.path.join(
                        output_dir, f"img_p{page_num}_{img_index}.{image_ext}"
                    )
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                # Tìm caption gần ảnh
                caption = _find_caption(page_text, img_index + 1)

                results.append({
                    "page_num": page_num,
                    "image_index": img_index,
                    "image_path": image_path,
                    "image_bytes": image_bytes,
                    "width": width,
                    "height": height,
                    "caption": caption,
                    "description": "",  # Vision LLM sẽ điền
                })

            except Exception as e:
                print(f"  Lỗi trích ảnh trang {page_num}, xref {xref}: {e}")

    doc.close()
    return results


def _find_caption(page_text: str, figure_num: int) -> str:
    """
    Tìm caption của Figure trong text trang.
    Pattern phổ biến: "Figure 1: ...", "Fig. 1. ...", "Figure 1. ..."
    """
    patterns = [
        rf"(?:Figure|Fig\.?)\s*{figure_num}\s*[:.]\s*(.+?)(?:\n|$)",
        rf"(?:Table)\s*{figure_num}\s*[:.]\s*(.+?)(?:\n|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()

    # Fallback: tìm bất kỳ "Figure X" nào
    general_pattern = r"(?:Figure|Fig\.?|Table)\s*\d+\s*[:.]\s*(.+?)(?:\n|$)"
    match = re.search(general_pattern, page_text, re.IGNORECASE)
    if match:
        return match.group(0).strip()

    return ""


def describe_image_with_vision_llm(
    image_bytes: bytes,
    caption: str = "",
    provider: str = "groq",
) -> str:
    """
    Gửi ảnh cho Vision LLM mô tả nội dung.

    Provider miễn phí:
    - "groq": Llama 3.2 90B Vision (Free tier)
    - "ollama": Llama 3.2 Vision (chạy local)

    Returns: Mô tả text của ảnh
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "Describe this figure from a scientific paper in detail. "
        "Focus on: methods shown, data/results presented, architecture diagrams, "
        "and any metrics or comparisons visible. "
        "Be specific about names of models, datasets, and numerical values."
    )
    if caption:
        prompt += f"\n\nThe figure caption is: \"{caption}\""

    if provider == "groq":
        return _describe_with_groq(image_b64, prompt)
    elif provider == "ollama":
        return _describe_with_ollama(image_b64, prompt)
    else:
        return f"[Image: {caption}]" if caption else "[Image without caption]"


def _describe_with_groq(image_b64: str, prompt: str) -> str:
    """Gọi Groq API với Llama 3.2 Vision (miễn phí)."""
    try:
        import os
        from groq import Groq

        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

        response = client.chat.completions.create(
            model="llama-3.2-90b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=500,
            temperature=0,
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"[Vision LLM error: {e}]"


def _describe_with_ollama(image_b64: str, prompt: str) -> str:
    """Gọi Ollama local với Llama 3.2 Vision (miễn phí, chạy trên máy)."""
    try:
        import httpx

        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

        response = httpx.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "llama3.2-vision",
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            },
            timeout=120,
        )

        return response.json().get("response", "")

    except Exception as e:
        return f"[Ollama Vision error: {e}]"


def process_images_for_pipeline(
    images: list[dict],
    use_vision_llm: bool = False,
    provider: str = "groq",
) -> str:
    """
    Xử lý tất cả ảnh trích xuất được → trả về text mô tả.

    Text này sẽ được gộp vào pipeline extraction giống text thường,
    LLM sẽ trích Entity/Relation từ mô tả ảnh.
    """
    descriptions = []

    for img in images:
        if use_vision_llm and img["image_bytes"]:
            # Mức 3: Dùng Vision LLM mô tả ảnh
            desc = describe_image_with_vision_llm(
                img["image_bytes"],
                img["caption"],
                provider=provider,
            )
        elif img["caption"]:
            # Mức 2: Chỉ dùng caption
            desc = img["caption"]
        else:
            # Mức 1: Bỏ qua
            continue

        descriptions.append(
            f"[Figure on page {img['page_num']}]: {desc}"
        )

    return "\n\n".join(descriptions)
