# Graph Schema — Knowledge Graph Structure

## Node Types (Thực thể)

| Node Label | Properties | Mô tả |
|------------|-----------|-------|
| **Paper** | `name`, `year`, `abstract`, `keywords` | Bài báo khoa học |
| **Author** | `name`, `affiliation` | Tác giả |
| **Method** | `name`, `description` | Phương pháp / Mô hình (VD: Transformer, BERT) |
| **Metric** | `name`, `value`, `description` | Chỉ số đánh giá (VD: BLEU, F1-score) |
| **Dataset** | `name`, `description`, `size` | Tập dữ liệu (VD: SQuAD, ImageNet) |
| **Task** | `name`, `description` | Bài toán (VD: NER, Machine Translation) |
| **Organization** | `name` | Tổ chức (VD: Google, OpenAI) |

## Edge Types (Quan hệ)

| Relation | Source → Target | Mô tả |
|----------|----------------|-------|
| **AUTHORED_BY** | Paper → Author | Tác giả viết bài báo |
| **CITES** | Paper → Paper | Bài báo trích dẫn bài khác |
| **USES_METHOD** | Paper → Method | Bài báo sử dụng phương pháp |
| **ACHIEVES_METRIC** | Paper → Metric | Bài báo đạt chỉ số |
| **EVALUATED_ON** | Paper → Dataset | Bài báo đánh giá trên dataset |
| **ADDRESSES_TASK** | Paper → Task | Bài báo giải quyết bài toán |
| **BELONGS_TO** | Author → Organization | Tác giả thuộc tổ chức |
| **IMPROVES** | Method → Method | Phương pháp cải tiến từ phương pháp khác |
| **COMPARED_WITH** | Method → Method | So sánh 2 phương pháp |

## Ví Dụ Cypher Queries

```cypher
// Tìm tất cả papers của 1 tác giả
MATCH (p:Paper)-[:AUTHORED_BY]->(a:Author {name: "Vaswani"})
RETURN p.name, p.year

// Tìm methods chung giữa 2 papers
MATCH (p1:Paper {name: "Attention Is All You Need"})-[:USES_METHOD]->(m)<-[:USES_METHOD]-(p2:Paper)
RETURN p2.name, m.name

// So sánh metrics giữa 2 methods
MATCH (p1:Paper)-[:USES_METHOD]->(m1:Method {name: "Transformer"})
MATCH (p1)-[:ACHIEVES_METRIC]->(metric)
RETURN p1.name, metric.name, metric.value
```

## Constraints & Indexes

```cypher
CREATE CONSTRAINT FOR (p:Paper) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT FOR (a:Author) REQUIRE a.name IS UNIQUE;
CREATE CONSTRAINT FOR (m:Method) REQUIRE m.name IS UNIQUE;
CREATE INDEX FOR (p:Paper) ON (p.year);
```
