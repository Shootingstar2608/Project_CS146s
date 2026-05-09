"""
Prompt Templates — Tập trung tất cả prompts 1 chỗ duy nhất.

Đã cập nhật theo schema_sample.md:
- 8 Entity types (Paper, Author, Organization, Conference, Topic, Methodology, Dataset, Result)
- 12 Relation types (AUTHORED, AFFILIATED_WITH, PUBLISHED_AT, COVERS_TOPIC, ...)
- Yêu cầu trích xuất aliases + edge properties
"""

EXTRACTION_PROMPT = """Bạn là chuyên gia trích xuất thông tin từ bài báo khoa học.

NHIỆM VỤ: Từ đoạn text bên dưới, hãy trích xuất:

## 1. Entities (Thực thể)
Mỗi entity cần có: `name` (tên canonical), `type`, `aliases` (tên gọi khác), `description`

**Loại entity:**
| Type | Ví dụ |
|------|-------|
| Paper | "Attention Is All You Need" |
| Author | "Ashish Vaswani", "Vaswani et al." |
| Organization | "Google Brain", "OpenAI" |
| Conference | "NeurIPS 2024", "ACL", "Nature" |
| Topic | "Natural Language Processing", "Computer Vision" |
| Methodology | "Transformer", "BERT", "Self-Attention" |
| Dataset | "SQuAD", "ImageNet", "WMT-14" |

## 2. Results (Kết quả metric)
Mỗi result cần: `metric_name`, `value`, `unit`, `context`
Ví dụ: metric_name="BLEU", value=28.4, unit="", context="on WMT-14 EN-DE"

## 3. Relations (Quan hệ)
Mối liên hệ giữa 2 entity. Cần có `evidence` (trích câu gốc).

**Loại relation:**
| Relation | Ý nghĩa | Ví dụ |
|----------|---------|-------|
| AUTHORED | Tác giả viết paper | Author → Paper |
| AFFILIATED_WITH | Thuộc tổ chức | Author → Organization |
| PUBLISHED_AT | Xuất bản tại | Paper → Conference |
| COVERS_TOPIC | Thuộc chủ đề | Paper → Topic |
| USES_METHOD | Sử dụng phương pháp | Paper → Methodology |
| EVALUATED_ON | Đánh giá trên dataset | Paper → Dataset |
| CITES | Trích dẫn paper khác | Paper → Paper |
| ACHIEVES | Đạt kết quả | Paper → Result |
| SUBTOPIC_OF | Chủ đề con | Topic → Topic |
| VARIANT_OF | Biến thể của method | Methodology → Methodology |

**Edge properties** (nếu có):
- AUTHORED: `role` = "first_author" / "co_author" / "corresponding"
- USES_METHOD: `role` = "proposed" / "baseline" / "component"
- COVERS_TOPIC: `relevance` = 0.0 - 1.0

## QUY TẮC QUAN TRỌNG:
1. KHÔNG chunk hay tóm tắt văn bản. Chỉ trích xuất entity + relation.
2. Tên entity phải NHẤT QUÁN (dùng canonical form, ghi aliases riêng).
3. Mỗi relation PHẢI có evidence (câu gốc từ text).
4. Nếu không chắc chắn, KHÔNG trích xuất (precision > recall).
5. Kết quả metric phải có GIÁ TRỊ SỐ cụ thể.

Trả về JSON theo schema đã cho."""

METADATA_PROMPT = """Từ phần đầu bài báo khoa học bên dưới, trích xuất thông tin định danh bài báo.

QUY TẮC PHÂN LOẠI DANH MỤC (categories):
- Bạn CÓ THỂ và NÊN chọn nhiều danh mục nếu bài báo thuộc về nhiều lĩnh vực (Ví dụ: Một bài báo về AI trên thiết bị nhúng thì chọn cả "ML/AI" và "IoT/Hardware").
- Danh sách danh mục được phép: "ML/AI", "IoT/Hardware", "Networks", "Theory", "Surveys".
- Trả về kết quả dưới dạng mảng (Array), ví dụ: ["ML/AI", "IoT/Hardware"].

THÔNG TIN CẦN TRÍCH XUẤT:
- title: Tên bài báo
- authors: Danh sách tác giả
- categories: Mảng các danh mục phù hợp.
- year: Năm xuất bản (số nguyên)
- abstract: Tóm tắt bài báo
- keywords: Các từ khóa quan trọng
- venue: Nơi xuất bản
- doi: DOI bài báo

VÍ DỤ:
Đầu vào: "Edge Intelligence: Paving the Last Mile of Artificial Intelligence with Edge Computing. Abstract: This paper discusses deploying Deep Learning models on IoT devices..."
Đầu ra mong muốn: { "categories": ["ML/AI", "IoT/Hardware"], ... }

Trả về JSON nguyên bản, không giải thích thêm."""

RESOLUTION_PROMPT = """Bạn là chuyên gia Entity Resolution.

Cho 2 thực thể sau đây:
- Entity A: "{entity_a}" (loại: {type_a})
- Entity B: "{entity_b}" (loại: {type_b})
- Similarity score: {score}

Hãy xác định liệu 2 thực thể này có đại diện cho CÙNG MỘT thứ không.

Ví dụ:
- "GPT-4" và "GPT-4 Model" → CÓ (cùng 1 model, "GPT-4 Model" là alias)
- "BERT" và "RoBERTa" → KHÔNG (2 model khác nhau)
- "Vaswani et al." và "Ashish Vaswani" → CÓ (cùng 1 tác giả)
- "NeurIPS" và "NIPS" → CÓ (cùng 1 hội nghị, đổi tên)
- "NLP" và "Natural Language Processing" → CÓ (viết tắt)

Trả lời JSON: is_same (bool), reasoning (giải thích ngắn)."""
