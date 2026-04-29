# Architecture Document (Bản Nháp)

## Autonomous Graph-RAG Agent — Kiến Trúc Hệ Thống

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
│   Neo4j (Knowledge Graph)  │  PostgreSQL (Metadata)     │
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
  → FastAPI nhận qua WebSocket
  → Security: check Prompt Injection + mask PII
  → LangGraph Agent:
      1. Planner: phân tích câu hỏi → lập kế hoạch N bước
      2. Retriever: LLM sinh Cypher → query Neo4j
      3. Synthesizer: tổng hợp context → sinh câu trả lời
      4. Validator: kiểm tra chất lượng → loop lại nếu thiếu
  → Streaming response về Frontend
  → Frontend hiển thị: text + Graph Visualization (highlight nodes)
```

### 3. Tech Stack

| Component | Technology | Lý do |
|-----------|-----------|-------|
| Graph DB | Neo4j Community | Tiêu chuẩn cho Knowledge Graph |
| Relational DB | PostgreSQL | Metadata, chat history |
| Backend | FastAPI | Async native, auto OpenAPI docs |
| Agent | LangGraph | Cyclic graph cho multi-step reasoning |
| LLM | Groq (Llama 3.3 70B) | Free tier, nhanh |
| PDF Parse | PyMuPDF | Xử lý 2 cột, bảng, miễn phí |
| Task Queue | Celery + Redis | Background processing |
| Frontend | Next.js + react-force-graph | SSR + Graph visualization |
| Proxy | Nginx | Reverse proxy, WebSocket support |

### 4. Graph Schema

Xem chi tiết tại [graph_schema.md](./graph_schema.md)
