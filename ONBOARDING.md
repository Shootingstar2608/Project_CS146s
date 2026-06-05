# Project CS146s — Engineering Onboarding

> **Audience:** A coding agent or engineer joining this repo cold. Read this top-to-bottom and you should be able to navigate, run, and contribute without further context. Citations like `path:line` point at the source of every claim so you can verify quickly.

---

## 1. TL;DR

A **Hybrid GraphRAG** (Graph-based Retrieval-Augmented Generation) research assistant. It ingests academic PDFs, builds a Neo4j knowledge graph (papers, authors, organizations, methods, datasets, results, …), indexes chunk embeddings in FAISS, and answers questions with a multi-step **LangGraph** agent that **fuses graph (Cypher) and vector retrieval** before an LLM synthesizes a cited answer.

- **Status:** End-to-end functional. Backend (FastAPI), frontend (Next.js), ingestion pipeline, hybrid retrieval, and the agent are all implemented and wired through Docker Compose. The headline flows (upload → ingest → graph/chat) work.
- **Demo-friendly defaults:** a deterministic **hashing embedder** and a committed FAISS index (`data/faiss_index/`) let the stack run with no model downloads, and the agent **falls back to local vector retrieval** when no LLM key is configured (`agent/graph.py:63`, `pipeline/embedding/embedder.py:75`).
- **Target users:** Researchers/students querying scientific paper corpora with relational ("which papers using Transformer evaluate on SQuAD?") rather than keyword retrieval.
- **Primary language of comments/docs:** Vietnamese. Code identifiers are English. Both are intentional — preserve them.

---

## 2. Quick Facts

| Item | Value | Source |
|---|---|---|
| Backend language | Python 3.11 (Docker image), 3.11+ | `backend/Dockerfile:5` |
| Backend framework | FastAPI 0.115 + Uvicorn (async) | `backend/requirements.txt:2-3` |
| Agent framework | LangGraph 0.3.5 + LangChain 0.3 | `backend/requirements.txt:25-34` |
| LLM provider | Groq (Llama 3.3 70B) — Ollama optional; local fallback if unset | `backend/app/core/llm_client.py`, `.env.example:4-13` |
| Structured-output lib | `instructor` 1.7.2 | `backend/requirements.txt:34` |
| Vector store | FAISS `IndexFlatIP` + JSON metadata sidecar | `pipeline/embedding/vector_store.py` |
| Embedder | Deterministic hashing (default) or sentence-transformers | `pipeline/embedding/embedder.py` |
| Fusion | Reciprocal Rank Fusion + alpha weighting | `pipeline/retrieval/fusion.py` |
| Graph DB | Neo4j 5 Community + APOC | `docker-compose.yml:23-40` |
| Relational DB | PostgreSQL 15 (asyncpg) | `docker-compose.yml:42-58` |
| Task queue | Celery 5.4 + Redis 7 (with inline fallback) | `docker-compose.yml:96-111`, `backend/app/api/upload.py:114` |
| PDF parsing | PyMuPDF 1.25 (`fitz`) | `backend/requirements.txt:37` |
| Security | Custom regex prompt-injection guard + XSS/PII sanitizer | `backend/app/security/{prompt_guard,sanitizer}.py` |
| Frontend | Next.js 16 + React 19 + Tailwind 4 + React Query + Zustand | `frontend/package.json` |
| Graph viz | `react-force-graph-2d` (canvas) | `frontend/src/app/graph/page.tsx` |
| Reverse proxy | Nginx 1.27-alpine | `docker-compose.yml:127-137`, `infra/nginx/nginx.conf` |
| Test runner | pytest + pytest-asyncio | `backend/requirements.txt:40-41` |
| Linter | `ruff` 0.8.6 | `backend/requirements.txt:42` |
| Code size | ~55 Python files + Next.js app | `find . -name '*.py'` |
| Git history | 12 commits | `git rev-list --count HEAD` |

> Note: `alembic` is **not** in current dependencies; Postgres schema is created via `Base.metadata.create_all()` at startup (`backend/app/core/database.py`, `init_db()`). There is no migration tree. Presidio/`slowapi` (referenced in older drafts) are no longer used — the security layer is hand-rolled regex.

---

## 3. Problem & Domain

Traditional RAG chunks documents and retrieves by vector similarity, losing **inter-document structure** (citations, shared methods, comparable metrics). This project tackles that by:

1. **Extracting structured entities and relations** from scientific PDFs into a property graph.
2. **Reasoning over both the graph and vector chunks** with an agent that decomposes a user question into steps, runs Cypher + vector search per step, **fuses** the results, and synthesizes a cited answer.

Hard requirement in the extraction code: **no plain-text chunking for entity extraction** — extraction operates section-by-section and produces typed entities directly (`pipeline/extraction/prompts.py`, `pipeline/extraction/schemas.py`). Chunking (`pipeline/embedding/chunker.py`) exists only to build the **vector** index, a separate path.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND (Next.js 16)                   │
│   Library  │  Upload  │  Chat  │  Graph Visualization     │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (REST, axios + React Query)
┌──────────────────────▼──────────────────────────────────┐
│                   BACKEND (FastAPI)                      │
│  REST API  │  Security guard  │  Lifespan DB init         │
└──────┬──────────────┬───────────────────────────────────┘
       │              │
       ▼              ▼
┌──────────────┐ ┌────────────────────────────────────────┐
│ Celery Worker│ │         AI AGENT (LangGraph)            │
│ (or inline)  │ │   Plan → Retrieve (loop) → Synthesize   │
│ PDF Pipeline │ │   Retrieve = Cypher + Vector + RRF       │
└──────┬───────┘ └────────────────┬───────────────────────┘
       │                          │
       ▼                          ▼
┌──────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│  Neo4j (KG)  │  PostgreSQL (metadata)  │  FAISS (vectors) │
└──────────────────────────────────────────────────────────┘
```

### Flow A — Document ingestion (`backend/app/api/upload.py`)
```
POST /api/v1/upload/
  → validate (extension + MIME + %PDF- magic bytes + size limit)
  → save to UPLOAD_DIR, INSERT documents (status='processing')
  → dispatch Celery ingest_pdf_task(file_path, paper_id)
       └─ if Celery/Redis unavailable → run pipeline.embedding.ingest.ingest_pdf INLINE
  → return 201 UploadResponse (status='processing'|'completed'|'failed')
```
Ingestion parses the PDF, chunks + embeds into FAISS, extracts entities/relations, and MERGEs the Paper subgraph into Neo4j (`pipeline/embedding/ingest.py`, `pipeline/loader/neo4j_loader.py`).

### Flow B — Question answering (`backend/app/api/router_chat.py` → `agent/graph.py`)
```
POST /api/v1/chat/  { message, session_id?, top_k }
  → PromptGuard.verify_and_clean (XSS strip, PII mask, injection check → 403)
  → run_agent(): LangGraph  plan → retrieve(loop) → synthesize
       retrieve = LLM-generated Cypher → Neo4j  +  vector search → FAISS
                  then Reciprocal Rank Fusion (alpha-weighted) → LLM context
  → ChatResponse { answer, sources[], reasoning_steps[], graph_data }
  → if no LLM provider configured → local retrieval-only fallback answer
```
Chat is a **plain POST**, not WebSocket, and is **not** streamed today. The "Validator loop" in older diagrams is not implemented — the real router is `Plan → Retrieve ⇄ Retrieve → Synthesize → END` (`agent/graph.py:21-56`).

---

## 5. Repository Layout

```
Project_CS146s/
├── CLAUDE.md                  # Agent guide (read this + the import-path gotcha)
├── README.md                  # Vietnamese project overview
├── docker-compose.yml         # neo4j, postgres, redis, backend, celery-worker, frontend, nginx
├── Makefile                   # dev | stop | dev-backend | dev-frontend | test | seed | lint | clean | reset-db
├── .env.example               # Env template
│
├── docs/
│   ├── architecture.md        # System diagram + tech-stack rationale (Vietnamese)
│   └── graph_schema.md        # Neo4j node/edge types + Cypher (current, authoritative)
│
├── pipeline/                  # Ingestion + retrieval (importable standalone)
│   ├── ingestion/  pdf_parser.py (PyMuPDF, 2-column aware), image_extractor.py
│   ├── extraction/ schemas.py, prompts.py, entity_extractor.py (instructor-typed)
│   ├── embedding/  chunker.py, embedder.py (hashing default), vector_store.py (FAISS), ingest.py
│   ├── retrieval/  vector_retriever.py, graph_retriever.py, fusion.py (RRF+alpha), reranker.py, query_router.py
│   ├── loader/     neo4j_loader.py (bulk MERGE of paper subgraph)
│   └── resolution/ (reserved stub for entity dedup — currently empty)
│
├── agent/                     # LangGraph multi-step reasoning
│   ├── graph.py               # build_agent_graph() + run_agent() + local fallback
│   ├── state.py               # AgentState TypedDict
│   └── nodes/  planner.py, retriever.py (hybrid), synthesizer.py
│
├── backend/                   # FastAPI service
│   ├── Dockerfile             # python:3.11-slim, PYTHONPATH=/app/backend:/app
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # lifespan (init_db, Neo4j check), CORS, routers, /health, /health/full
│       ├── config.py          # pydantic-settings (LLM, DBs, embedding/FAISS/RRF/rerank)
│       ├── api/  upload.py, router_chat.py, router_documents.py, router_graph.py, router_files.py
│       ├── core/ database.py (async SQLAlchemy), neo4j_client.py (sync+async), llm_client.py, exceptions.py
│       ├── models/ db_models.py, schemas.py, entity_schemas.py
│       ├── security/ prompt_guard.py, sanitizer.py
│       └── workers/ celery_app.py (ingest_pdf_task)
│
├── frontend/                  # Next.js 16 / React 19 / Tailwind 4 app (see frontend/AGENTS.md)
│   └── src/
│       ├── app/    page.tsx (→ /papers), papers/, papers/[id]/, chat/, graph/, upload/, layout.tsx, globals.css
│       ├── components/ layout/{Sidebar,Topbar,MainLayout}, providers/ReactQueryProvider
│       └── lib/    api.ts (axios client), queries.ts (React Query hooks), research-store.ts (Zustand), utils.ts
│
├── infra/                     # nginx/nginx.conf, scripts/init_neo4j.cypher
├── data/                      # faiss_index/ (committed demo index), uploads/
└── tests/                     # test_week1.py (scaffold acceptance suite)
```

---

## 6. Tech Stack & Why

| Layer | Choice | Rationale |
|---|---|---|
| Graph DB | **Neo4j 5 + APOC** | Property graph; APOC for batch ops |
| Relational DB | **PostgreSQL 15 (asyncpg)** | Document metadata, chat history; async driver matches FastAPI |
| Vector store | **FAISS `IndexFlatIP`** | Exact cosine (L2-normalised), no training; swap to IVF for >1M chunks |
| Embedder | **Hashing (default) / sentence-transformers** | Hashing runs with no model download for demos |
| Backend | **FastAPI** | Async-native, auto OpenAPI |
| Agent | **LangGraph** | Cyclic graph for multi-step reasoning |
| LLM | **Groq Llama 3.3 70B** (Ollama alt) | Free tier, low latency |
| Structured output | **`instructor`** | Pydantic-typed LLM responses |
| PDF parsing | **PyMuPDF** | 2-column layouts, tables |
| Task queue | **Celery + Redis** | Background ingestion (inline fallback if unavailable) |
| Frontend | **Next.js 16 + React 19** | App Router, SSR, standalone Docker output |
| Graph viz | **react-force-graph-2d** | Canvas force-directed graph |
| Data fetching | **TanStack React Query** | Caching, loading/error states |
| Client state | **Zustand (persisted)** | Chat sessions in localStorage |
| Security | **Custom regex guard** | Injection patterns + XSS strip + email/phone PII masking |

---

## 7. Service Topology (Docker Compose)

`docker-compose.yml` defines 7 services, all buildable:

| Service | Image / Build | Ports | Purpose |
|---|---|---|---|
| `neo4j` | `neo4j:5-community` | 7474 (UI), 7687 (Bolt) | Knowledge graph (APOC enabled) |
| `postgres` | `postgres:15-alpine` | host 5433 → 5432 | Document metadata, chat sessions |
| `redis` | `redis:7-alpine` | 6379 | Celery broker |
| `backend` | `backend/Dockerfile` | 8000 | FastAPI app (Swagger at `/docs`) |
| `celery-worker` | `backend/Dockerfile` | — | `celery -A app.workers.celery_app worker` |
| `frontend` | `frontend/Dockerfile` | 3000 | Next.js UI (`NEXT_PUBLIC_API_URL`) |
| `nginx` | `nginx:1.27-alpine` | 80 | Reverse proxy |

Healthchecks gate `neo4j`/`postgres`/`redis`; `backend` + `celery-worker` wait on `service_healthy`. `./data` and the `upload_data` volume are shared between backend and worker so both see uploaded files and the FAISS index. The Neo4j init script is mounted at `infra/scripts/init_neo4j.cypher`.

---

## 8. Data Models

### 8.1 PostgreSQL (`backend/app/models/db_models.py`)
- `Document(id UUID-str PK, filename, original_path, status, entity_count, relation_count, error_message, uploaded_at, completed_at)` — `status ∈ processing|completed|failed`.
- `ChatSession(id, created_at)`, `ChatMessage(id, session_id, role, content, reasoning_steps, created_at)`.

Schema is created at startup by `init_db()` (no Alembic).

### 8.2 Neo4j Graph Schema
**Authoritative reference: `docs/graph_schema.md`** (kept current). Node labels: `Paper, Author, Organization, Conference, Topic, Task, Methodology, Dataset, Result` (plus `Entity` fallback). Edges: `AUTHORED, AFFILIATED_WITH, PUBLISHED_AT, COVERS_TOPIC, ADDRESSES_TASK, USES_METHOD, EVALUATED_ON, CITES, ACHIEVES, RESULT_ON, RESULT_WITH, SUBTOPIC_OF, VARIANT_OF, IMPROVES, COMPARED_WITH`. The live label/edge sets also appear in `agent/nodes/retriever.py` (`CYPHER_PROMPT`), `backend/app/api/router_graph.py` (`_LABEL_TO_KIND`), and `pipeline/loader/neo4j_loader.py` — keep all four in sync when the schema changes.

### 8.3 API DTOs (`backend/app/models/schemas.py`)
`UploadResponse`, `ChatRequest` (message, session_id?, top_k), `ChatResponse` (answer, sources[], reasoning_steps[], graph_data), `GraphNode`, `GraphEdge`, `GraphData`, `DocumentInfo`, `DocumentListResponse`.

### 8.4 Extraction schemas (`pipeline/extraction/schemas.py`)
Used as `response_model=` for `instructor` calls — the LLM's typed output contract (`Entity`, `Relation`, `ExtractionResult`, `PaperMetadata`).

---

## 9. API Surface

Base prefix `/api/v1` (registered in `backend/app/main.py:96-100`).

| Method | Path | Body / Params | Response |
|---|---|---|---|
| `POST` | `/upload/` | multipart PDF `file` | `UploadResponse` |
| `GET` | `/documents` | — | papers list (Postgres + Neo4j metadata join) |
| `DELETE` | `/documents/{doc_id}` | — | cascade delete (Postgres + Neo4j + FAISS + disk); 204 clean / 200 summary / 404 |
| `POST` | `/chat/` | `{message, session_id?, top_k}` | `{answer, sources, reasoning_steps, graph_data}` |
| `GET` | `/graph` | — | `{nodes[], links[]}` (≤200 nodes) |
| `GET` | `/graph/paper/{paper_id}` | — | subgraph around one paper |
| `GET` | `/files/{doc_id}/pdf` | — | PDF download (FileResponse) |
| `GET` | `/files/{doc_id}` | — | file metadata + download_url |
| `GET` | `/health`, `/health/full` | — | liveness / deep DB check |

`DELETE /documents/{doc_id}` cascades across all stores (Postgres row, on-disk PDF, Neo4j `Paper` node via `DETACH DELETE`, and FAISS chunks via index rebuild). FAISS mutations are serialised through `vector_store_lock` (`pipeline/embedding/vector_store.py`), shared with the ingest write path. The frontend calls it through an optimistic React Query mutation (`frontend/src/lib/queries.ts` → `useDeleteDocument`).

---

## 10. Agent Flow (LangGraph)

### State (`agent/state.py`)
`AgentState` carries `messages`, `user_query`, `plan`, `current_step`, `retrieved_context`, `final_answer`, `graph_data`, `needs_more_info`, plus hybrid params `alpha` and `top_k`.

### Topology (`agent/graph.py`)
`planner_node → retrieve →(should_continue loop)→ retrieve | synthesize → END`. The router loops `retrieve` while `current_step < len(plan)`.

### Nodes
| Node | File | Does |
|---|---|---|
| `planner_node` | `agent/nodes/planner.py` | LLM → numbered plan |
| `retrieve` | `agent/nodes/retriever.py` | LLM → Cypher → Neo4j **and** vector search → FAISS, then RRF fuse → context |
| `synthesize` | `agent/nodes/synthesizer.py` | LLM → final markdown answer over fused context |

### Entry point & fallback
`run_agent(user_query, alpha_override?, top_k=5)` (`agent/graph.py:192`) compiles the graph once and `ainvoke`s it. If the LLM provider is unavailable (no `GROQ_API_KEY`, connection refused), it returns a **local vector-retrieval-only** answer instead of erroring (`agent/graph.py:63-189`).

---

## 11. Environment Variables (`.env.example`, `backend/app/config.py`)

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` \| `ollama` |
| `GROQ_API_KEY` | — | Required for full agent; unset → local fallback |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | when `LLM_PROVIDER=ollama` |
| `NEO4J_URI/USER/PASSWORD` | `bolt://neo4j:7687` / `neo4j` / `graphrag_secret_2024` | |
| `POSTGRES_URL` | `postgresql+asyncpg://…@postgres:5432/graphrag` | async driver |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker |
| `CORS_ORIGINS` | `["http://localhost:3000", …]` | JSON array |
| `UPLOAD_DIR` | `/app/data/uploads` | |
| `MAX_UPLOAD_SIZE_MB` | `50` | |
| `EMBEDDING_MODEL` | `hashing` | set to a sentence-transformers name for real embeddings |
| `FAISS_INDEX_PATH` | `/app/data/faiss_index` | |
| `CHUNK_SIZE`/`CHUNK_OVERLAP` | `512`/`64` | |
| `RRF_K` | `60` | fusion constant |
| `RERANK_ENABLED` | `false` | cross-encoder rerank (optional) |

---

## 12. Run / Dev Commands

From `Makefile`:
```bash
make dev          # docker compose up --build (full stack)
make stop         # docker compose down
make dev-backend  # uvicorn app.main:app --reload  (run inside backend/, needs PYTHONPATH — see §13)
make dev-frontend # cd frontend && npm run dev
make test         # python -m pytest tests/ -v
make seed         # ingest data/sample_papers into FAISS + Neo4j
make lint         # ruff check --fix across backend/, pipeline/, agent/
make clean        # compose down -v --rmi local + clear __pycache__
make reset-db     # wipe Neo4j + Postgres docs + uploads (containers stay up)
```

Services: frontend `:3000`, backend `:8000` (`/docs`), Neo4j UI `:7474`, Postgres host `:5433`, Redis `:6379`.

---

## 13. The import-path gotcha (read before running outside Docker)

Modules mix **two** import roots:
- `from app.config import …`, `from app.core… import …` → needs **`backend/`** on `PYTHONPATH`.
- `from backend.app… import …`, `from agent…`, `from pipeline…` → needs the **repo root** on `PYTHONPATH`.

Both must be present. Docker sets `PYTHONPATH=/app/backend:/app` (`backend/Dockerfile:32`). Locally:
```bash
PYTHONPATH=backend:. python -m pytest tests/ -v
PYTHONPATH=backend:. python -c "from pipeline.embedding.ingest import ingest_directory; ingest_directory('data/sample_papers')"
```
These `app.*`/`backend.app.*` imports are done **lazily inside functions** to avoid `agent ↔ pipeline ↔ backend` import cycles. Preserve that pattern.

---

## 14. Implementation Status

### ✅ Implemented & wired
- Ingestion: `pipeline/ingestion`, `pipeline/extraction`, `pipeline/embedding`, `pipeline/loader`.
- Hybrid retrieval: `pipeline/retrieval/{vector_retriever,graph_retriever,fusion,reranker,query_router}`.
- Agent: `agent/{graph,state}` + all three nodes (with local LLM fallback).
- Backend: `main.py`, `config.py`, all `api/` routers, `core/` clients, `models/`, `security/`, `workers/celery_app.py`.
- Frontend: full Next.js app (library, upload, chat, graph, paper detail).
- Infra: `backend/Dockerfile`, `frontend/Dockerfile`, `infra/nginx/nginx.conf`, `infra/scripts/init_neo4j.cypher`.
- Demo data: committed FAISS index at `data/faiss_index/`.

### ⚠️ Partial / reserved
- `pipeline/resolution/` — empty stub (entity dedup not implemented; loader MERGEs by name/id instead).
- Validator/quality-loop node — not implemented (diagram aspiration only).
- Chat streaming + WebSocket — not implemented (plain POST).
- Alembic migrations — none; `Base.metadata.create_all()` at startup.

---

## 15. Test Suite

`tests/test_week1.py` — 14 standalone acceptance checks (manual `try/except` style) split into "Team Leader" (repo structure, docs content, agent graph compiles) and "Data Engineer" (PDF parse of `Đề tài.pdf`, extraction schemas, prompt content) groups. They assert structural contracts only — **no** LLM/Neo4j/Postgres/Celery calls. Requires `Đề tài.pdf` at the repo root (gitignored prof brief) for the parsing checks. Run with the PYTHONPATH from §13.

---

## 16. Implicit Conventions (preserve these)

1. **Bilingual code** — English identifiers; Vietnamese comments, docstrings, and LLM prompts. Don't translate existing Vietnamese.
2. **Async backend** — FastAPI routes, async SQLAlchemy, asyncpg. `Neo4jClient.execute_query` is **synchronous**, called directly from async code; keep Neo4j calls quick or offload to Celery.
3. **No plain-text chunking for entity extraction** — section-by-section typed extraction. Chunking is only for the vector index.
4. **Pydantic-typed LLM output via `instructor`** — never hand-parse model JSON.
5. **Hybrid retrieval** = RRF of vector + KG with `alpha` weight (0=graph-only, 1=vector-only, default 0.5).
6. **Demo-safe defaults** — hashing embedder + committed FAISS index + LLM fallback so the stack runs without external setup.
7. **UUID string PKs**, **UTC timestamps**, settings via `get_settings()` (lru-cached).

---

## 17. Glossary

| Term | Meaning here |
|---|---|
| **GraphRAG** | RAG where retrieval is over a structured graph (here, fused with vector chunks) |
| **RRF** | Reciprocal Rank Fusion — merges two ranked lists by `Σ 1/(k+rank)` |
| **alpha** | Weight shifting fusion between vector (1.0) and graph (0.0) |
| **Cypher** | Neo4j's query language |
| **`instructor`** | Wraps an LLM call, validating output against a Pydantic schema |
| **APOC** | Neo4j "Awesome Procedures On Cypher" plugin |
| **`Đề tài.pdf`** | "Project topic.pdf" — the gitignored professor brief referenced by tests |

---

*Last verified 2026-06-04 against a cold read of the repo. Verify any claim against the cited file paths before depending on it.*
