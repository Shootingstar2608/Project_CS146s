# Project CS146s - GraphRAG System

##  Tổng quan dự án (Project Overview)

Dự án này là một hệ thống **GraphRAG** (Graph-based Retrieval-Augmented Generation) hoàn chỉnh, kết hợp sức mạnh của Knowledge Graph (Đồ thị tri thức) và các mô hình ngôn ngữ lớn (LLMs). Hệ thống cho phép trích xuất thông tin từ các tài liệu (như PDF), xây dựng đồ thị tri thức, và cung cấp khả năng truy vấn dữ liệu phức tạp dựa trên đồ thị để mang lại câu trả lời chính xác, giàu ngữ cảnh hơn so với RAG truyền thống.

---

##  Hệ thống kiến trúc (Architecture)

Hệ thống được thiết kế theo kiến trúc Microservices và được đóng gói hoàn toàn bằng Docker, bao gồm các thành phần chính sau:

### 1. Frontend (Next.js)
- Ứng dụng web giao diện người dùng được xây dựng bằng **Next.js**.
- Cung cấp giao diện tương tác cho người dùng để tải lên tài liệu, thực hiện truy vấn RAG, và trực quan hóa các node/edge của đồ thị tri thức.
- Tương tác với hệ thống qua các API RESTful của Backend.

### 2. Backend (FastAPI)
- Core API được xây dựng bằng **FastAPI** hỗ trợ xử lý bất đồng bộ (async).
- Đóng vai trò là cửa ngõ giao tiếp, tiếp nhận các yêu cầu truy vấn, xử lý luồng agent, cung cấp API cho frontend.
- Tích hợp **LangChain**, **LangGraph** để điều phối logic của LLM Agent.
- Cung cấp tính năng bảo mật như rate-limiting (`slowapi`) và anonymization PII dữ liệu (Presidio).

### 3. Asynchronous Worker (Celery + Redis)
- **Celery Worker**: Đảm nhiệm các tác vụ tốn thời gian chạy ngầm (background jobs) như: xử lý file PDF (`PyMuPDF`), bóc tách thực thể (Extraction), xây dựng và lưu trữ dữ liệu vào Knowledge Graph.
- **Redis**: Đóng vai trò là Message Broker (hàng đợi tác vụ) cho Celery và có thể dùng làm Cache.

### 4. Databases (Lưu trữ)
- **Neo4j**: Đồ thị tri thức (Knowledge Graph Database) lưu trữ các thực thể (Entities) và mối quan hệ (Relationships) được trích xuất từ tài liệu. Hỗ trợ Plugin APOC.
- **PostgreSQL**: Cơ sở dữ liệu quan hệ lưu trữ metadata chứa thông tin về tài liệu đã tải lên, lịch sử người dùng và cấu hình ứng dụng (sử dụng SQLAlchemy và Asyncpg).

### 5. Data Pipeline & Agent Core
- **Pipeline (`pipeline/`)**: Luồng nạp dữ liệu bao gồm các bước: `loader` (đọc text), `extraction` (rút trích thực thể, quan hệ với sự hỗ trợ của LLM - Groq), `resolution` (giải quyết xung đột/trùng lặp thực thể), và `ingestion` (đưa vào đồ thị).
- **Agent (`agent/`)**: Trái tim thông minh của hệ thống sử dụng **LangGraph** với sự kết hợp của các `tools` và `nodes` để quyết định bước lấy dữ liệu nào là tối ưu khi người dùng đặt câu hỏi.

---

##  Cấu trúc thư mục (Directory Structure)

```text
project_CS146s/
├── agent/            # Logic của LLM Agents, điều phối node & tool bằng LangGraph
├── backend/          # Chứa source code FastAPI (app/, config, core/, api/) và Worker
├── frontend/         # Chứa source code Next.js UI
├── pipeline/         # Xử lý luồng dữ liệu: loader, extraction, resolution, ingestion
├── infra/            # Các file cấu hình hạ tầng mạng, Nginx reverse proxy, Init DB scripts
├── data/             # Thư mục lưu trữ data nội bộ, file upload
├── docs/             # Tài liệu dự án
├── docker-compose.yml# File cấu hình khởi chạy toàn bộ dịch vụ docker
├── Makefile          # Định nghĩa các command chạy nhanh (nếu có)
└── README.md         # Tài liệu tổng quan (file này)
```

---

## 🚀 Hướng dẫn khởi chạy (Getting Started)

Hệ thống được đóng gói 100% bằng Docker và Docker Compose.

**1. Chuẩn bị biến môi trường:**
Tạo file `.env` dựa trên file mẫu:
```bash
cp .env.example .env
```
*(Điền các thông tin cần thiết vào `.env` như API Key của Groq, mật khẩu database...)*

**2. Khởi chạy toàn bộ hệ thống bằng Docker Compose:**
```bash
docker-compose up --build -d
```

**Các dịch vụ sẽ có sẵn tại:**
- **Frontend App:** http://localhost:3000
- **Backend API Docs (Swagger):** http://localhost:8000/docs
- **Neo4j Browser:** http://localhost:7474 (Bolt: 7687)
- **PostgreSQL:** Port `5432`
- **Redis:** Port `6379`

Để dừng ứng dụng:
```bash
docker-compose down
```
