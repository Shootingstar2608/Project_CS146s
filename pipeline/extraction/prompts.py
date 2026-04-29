"""
Prompt Templates — Tập trung tất cả prompts 1 chỗ duy nhất.
"""

EXTRACTION_PROMPT = """Bạn là chuyên gia trích xuất thông tin từ bài báo khoa học.

NHIỆM VỤ: Từ đoạn text bên dưới, hãy trích xuất:
1. **Entities** (Thực thể) — mỗi entity có: name, type, description
   - Loại: Paper, Author, Method, Metric, Dataset, Task, Organization
2. **Relations** (Quan hệ) — mối liên hệ giữa 2 entity
   - Loại: CITES, USES_METHOD, ACHIEVES_METRIC, AUTHORED_BY, EVALUATED_ON, BELONGS_TO, IMPROVES, COMPARED_WITH

QUY TẮC:
- KHÔNG chunk hay tóm tắt văn bản. Chỉ trích xuất entity + relation.
- Tên entity phải nhất quán (luôn dùng "Transformer", không dùng "transformer model" lẫn lộn).
- Mỗi relation phải có evidence (câu gốc từ text).
- Nếu không chắc chắn, KHÔNG trích xuất.

Trả về JSON theo schema đã cho."""

METADATA_PROMPT = """Từ phần đầu bài báo khoa học bên dưới, trích xuất:
- title: Tên bài báo
- authors: Danh sách tác giả
- year: Năm xuất bản (nếu có)
- abstract: Tóm tắt
- keywords: Từ khóa (nếu có)

Trả về JSON theo schema đã cho."""
