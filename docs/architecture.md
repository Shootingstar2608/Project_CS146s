# Architecture Document

## Autonomous Graph-RAG Agent — Kiến Trúc Hệ Thống

> **Trạng thái:** Một số chi tiết trong bản nháp gốc đã được cập nhật cho khớp code hiện tại.
> Khác biệt chính so với bản nháp: Chat dùng **REST POST** (chưa có WebSocket/streaming),
> Retriever là **hybrid** (Cypher trên Neo4j **+** vector search trên FAISS rồi fuse bằng RRF),
> và node **Validator** trong sơ đồ **chưa được hiện thực**. Xem `ONBOARDING.md` và `docs/graph_schema.md`.

### 1. Tổng Quan

Hệ thống gồm 4 tầng chính, giao tiếp qua REST API và message queue:

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                   │
│   Chat UI  │  File Upload  │  Graph Visualization       │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                   BACKEND (FastAPI)                      │
│   REST API  │  WebSocket Handler  │  Security Layer      │
└──────┬──────────────┬───────────────────────────────────┘
       │              │
       ▼              ▼
┌──────────────┐ ┌────────────────────────────────────────┐
│ Celery Worker│ │         AI AGENT (LangGraph)            │
│ (Background) │ │  Planner → Retriever → Synthesizer     │
│              │ │           ↑       ↓                     │
│ PDF Pipeline │ │         Validator (loop)                │
└──────┬───────┘ └────────────────┬───────────────────────┘
       │                          │
       ▼                          ▼
┌──────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│  Neo4j (KG)  │  PostgreSQL (Metadata)  │  FAISS (Vectors) │
└──────────────────────────────────────────────────────────┘
```

### 2. Luồng Dữ Liệu

#### Luồng 1: Upload PDF → Xây dựng Knowledge Graph
```
User upload PDF
  → FastAPI validate (Magic bytes)
  → Lưu metadata vào PostgreSQL (status: processing)
  → Đẩy task vào Celery queue
  → [Background] PyMuPDF parse PDF 2 cột
  → [Background] LLM trích xuất Entities & Relations (JSON)
  → [Background] Entity Resolution (Fuzzy + LLM verify)
  → [Background] Bulk insert vào Neo4j
  → Cập nhật PostgreSQL (status: completed)
  → Thông báo Frontend qua WebSocket
```

#### Luồng 2: Chat → Agent suy luận đa bước
```
User gửi câu hỏi
  → FastAPI nhận qua REST POST /api/v1/chat/   (chưa dùng WebSocket)
  → Security: check Prompt Injection + mask PII (regex tự viết)
  → LangGraph Agent:
      1. Planner: phân tích câu hỏi → lập kế hoạch N bước
      2. Retriever (hybrid): LLM sinh Cypher → Neo4j  +  vector search → FAISS
                              rồi fuse bằng Reciprocal Rank Fusion (alpha-weighted)
      3. Synthesizer: tổng hợp context → sinh câu trả lời (markdown)
      (Validator: dự kiến kiểm tra chất lượng — CHƯA hiện thực)
  → Response JSON về Frontend (chưa streaming)
  → Frontend hiển thị: text + Graph Visualization
  → Nếu chưa cấu hình LLM → fallback trả lời bằng vector retrieval local
```

### 3. Tech Stack

| Component | Technology | Lý do |
|-----------|-----------|-------|
| Graph DB | Neo4j Community | Tiêu chuẩn cho Knowledge Graph |
| Relational DB | PostgreSQL | Metadata, chat history |
| Vector Store | FAISS (IndexFlatIP) | Semantic search, fuse với KG bằng RRF |
| Embedder | Hashing (mặc định) / sentence-transformers | Chạy demo không cần tải model |
| Backend | FastAPI | Async native, auto OpenAPI docs |
| Agent | LangGraph | Cyclic graph cho multi-step reasoning |
| LLM | Groq (Llama 3.3 70B) | Free tier, nhanh |
| PDF Parse | PyMuPDF | Xử lý 2 cột, bảng, miễn phí |
| Task Queue | Celery + Redis | Background processing |
| Frontend | Next.js 16 + React Query + react-force-graph | SSR + caching + Graph visualization |
| Proxy | Nginx | Reverse proxy |

### 4. Graph Schema

Xem chi tiết tại [graph_schema.md](./graph_schema.md)
