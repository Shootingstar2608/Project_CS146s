# Project CS146s — Engineering Onboarding

> **Audience:** A coding agent or engineer joining this repo cold. Read this top-to-bottom and you should be able to navigate, run, and contribute without further context. Citations like `path:line` point at the source of every claim so you can verify quickly.

---

## 1. TL;DR

A **Graph-based Retrieval-Augmented Generation (GraphRAG)** system that ingests scientific PDFs, builds a Neo4j knowledge graph of papers/authors/methods/metrics/datasets/tasks, and answers user questions through a multi-step LangGraph agent that plans queries, runs Cypher against the graph, and synthesizes natural-language answers.

- **Status:** Mid-scaffold. Pipeline + agent skeleton implemented; backend service layer (FastAPI app, DB clients, Celery worker registration) is empty/stubbed; `frontend/` and `infra/` directories don't exist yet despite being referenced.
- **Target users:** Researchers/students querying scientific paper corpora with relational ("which papers using Transformer evaluate on SQuAD?") rather than keyword retrieval.
- **Owner:** Senior engineer (the user's senior); this codebase scaffolds the project for a multi-person team — see §17 *Team Roles*.
- **Primary language of comments/docs:** Vietnamese. Code identifiers are English. Both must be preserved.

---

## 2. Quick Facts

| Item | Value | Source |
|---|---|---|
| Languages | Python 3.12+ (only) | `backend/requirements.txt` |
| Backend framework | FastAPI 0.115 + Uvicorn (async) | `backend/requirements.txt:2-3` |
| Agent framework | LangGraph 0.3.5 + LangChain-Core 0.3.28 | `backend/requirements.txt:20-21` |
| LLM provider | Groq (Llama 3.3 70B) — Ollama optional | `.env.example:5-13` |
| Structured-output lib | `instructor` 1.7.2 | `backend/requirements.txt:24` |
| Graph DB | Neo4j 5 Community + APOC | `docker-compose.yml:5-21` |
| Relational DB | PostgreSQL 15 (asyncpg) | `docker-compose.yml:23-39` |
| Task queue | Celery 5.4 + Redis 7 | `docker-compose.yml:41-92` |
| PDF parsing | PyMuPDF 1.25 (`fitz`) | `backend/requirements.txt:27` |
| PII / safety | Presidio (analyzer + anonymizer), `slowapi`, `python-magic` | `backend/requirements.txt:30-33` |
| Frontend (planned) | Next.js + react-force-graph | `docs/architecture.md:65-77` |
| Reverse proxy | Nginx 1.27-alpine (config not present) | `docker-compose.yml:108-118` |
| Test runner | pytest + pytest-asyncio | `backend/requirements.txt:36-37` |
| Linter | `ruff` 0.8.6 | `backend/requirements.txt:38` |
| File count | 76 files / 35 Python files | `find . -type f \| wc -l` |
| Git history | 3 commits — `cd6c190 full ingestion`, `023f330 add readme`, `65df886 Scaffold repo` | `git log --oneline` |

---

## 3. Problem & Domain

Traditional RAG chunks documents and retrieves by vector similarity, losing **inter-document structure** (citations, shared methods, comparable metrics). This project tackles that by:

1. **Extracting structured entities and relations** from scientific PDFs into a property graph instead of flat text chunks.
2. **Reasoning over the graph** with an agent that decomposes a user question into multi-step Cypher queries, then synthesizes a cited answer.

Example queries the system is meant to answer (`docs/graph_schema.md:30-44`):

```cypher
// All papers by Vaswani
MATCH (p:Paper)-[:AUTHORED_BY]->(a:Author {name: "Vaswani"})
RETURN p.name, p.year

// Methods two papers share
MATCH (p1:Paper {name: "Attention Is All You Need"})-[:USES_METHOD]->(m)<-[:USES_METHOD]-(p2:Paper)
RETURN p2.name, m.name
```

Hard requirement called out in the extraction code: **no plain-text chunking** — extraction operates section-by-section and produces typed entities directly (`pipeline/extraction/schemas.py:5-6`, `pipeline/extraction/prompts.py:14`).

---

## 4. Architecture

From `docs/architecture.md:9-33`:

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                    │  ← does not exist yet
│   Chat UI  │  File Upload  │  Graph Visualization        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                   BACKEND (FastAPI)                      │  ← skeleton only
│   REST API  │  WebSocket Handler  │  Security Layer      │
└──────┬──────────────┬───────────────────────────────────┘
       │              │
       ▼              ▼
┌──────────────┐ ┌────────────────────────────────────────┐
│ Celery Worker│ │         AI AGENT (LangGraph)            │
│ (Background) │ │  Planner → Retriever → Synthesizer      │
│              │ │           ↑       ↓                     │
│ PDF Pipeline │ │         Validator (loop)                │  ← Validator not yet implemented
└──────┬───────┘ └────────────────┬───────────────────────┘
       │                          │
       ▼                          ▼
┌──────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│   Neo4j (Knowledge Graph)  │  PostgreSQL (Metadata)      │
└──────────────────────────────────────────────────────────┘
```

Two end-to-end flows the system implements (or intends to):

### Flow A — Document ingestion
```
User uploads PDF
  → FastAPI validates (magic bytes via python-magic)        [stubbed]
  → INSERT INTO documents (status='processing')             [stubbed]
  → Push to Celery queue                                    [stubbed]
  → [worker] PyMuPDF parses 2-column PDF (sort=True)        [✓ implemented]
  → [worker] split_into_sections by heading regex           [✓ implemented]
  → [worker] LLM (instructor + Groq) → ExtractionResult     [✓ implemented]
  → [worker] Entity Resolution (fuzzy + LLM verify)         [stubbed - empty dir]
  → [worker] Bulk MERGE into Neo4j                          [stubbed]
  → UPDATE documents SET status='completed'                 [stubbed]
  → WebSocket push notification to frontend                 [stubbed]
```

### Flow B — Question answering
```
User sends question over WebSocket
  → FastAPI route                                           [stubbed]
  → Security: prompt-injection check + PII masking          [stubbed - Presidio in deps]
  → LangGraph agent (compiled in agent/graph.py:55-59):
      1. plan_steps      → produces N-step plan              [✓ wired, depends on llm_client]
      2. retrieve loop   → LLM-generated Cypher → Neo4j      [✓ wired, depends on llm_client + Neo4jClient]
      3. synthesize      → final answer in markdown          [✓ wired, depends on llm_client]
  → Streaming response back to frontend                     [stubbed]
```

The "Validator (loop)" node mentioned in the architecture diagram is **not implemented** — the actual graph is `Plan → Retrieve ⇄ Retrieve → Synthesize → END` with a counter-based router, not a quality validator (`agent/graph.py:20-55`).

---

## 5. Repository Layout

```
Project_CS146s/
├── README.md                  # Vietnamese project overview (entry point for humans)
├── docker-compose.yml         # 6 services: neo4j, postgres, redis, backend, celery-worker, frontend, nginx
├── Makefile                   # `make dev | stop | dev-backend | dev-frontend | test | seed | lint | clean`
├── .env.example               # Env template — Groq/Ollama, Neo4j, Postgres, Redis, upload paths
├── .gitignore
│
├── docs/
│   ├── architecture.md        # System diagrams + tech-stack rationale (Vietnamese)
│   └── graph_schema.md        # Neo4j node/edge types + example Cypher (Vietnamese)
│
├── pipeline/                  # Document ingestion → entity extraction → graph load
│   ├── ingestion/
│   │   ├── pdf_parser.py      # ✓ parse_pdf() + split_into_sections() — PyMuPDF, 2-column aware
│   │   └── image_extractor.py # ✓ Image extraction + optional Vision-LLM captioning
│   ├── extraction/
│   │   ├── schemas.py         # ✓ Pydantic: Entity, Relation, ExtractionResult, PaperMetadata
│   │   ├── prompts.py         # ✓ EXTRACTION_PROMPT, METADATA_PROMPT (Vietnamese, instructs LLM)
│   │   └── entity_extractor.py# ✓ extract_entities_from_text(), extract_paper_metadata()
│   ├── loader/                # STUB — empty __init__.py, intended for graph-load step
│   └── resolution/            # STUB — empty __init__.py, intended for entity dedup
│
├── agent/                     # LangGraph multi-step reasoning
│   ├── graph.py               # ✓ build_agent_graph() — StateGraph compile + run_agent()
│   ├── state.py               # ✓ AgentState TypedDict
│   ├── nodes/
│   │   ├── planner.py         # ✓ plan_steps() — LLM produces numbered plan
│   │   ├── retriever.py       # ✓ retrieve_from_graph() — LLM → Cypher → Neo4j
│   │   └── synthesizer.py     # ✓ synthesize_answer() — LLM tool synthesis from context
│   └── tools/                 # STUB — empty
│
├── backend/                   # FastAPI service
│   ├── requirements.txt       # ✓ Pinned dep manifest (used by Dockerfile, but Dockerfile is missing)
│   └── app/
│       ├── main.py            # STUB — empty; supposed to be FastAPI entrypoint
│       ├── config.py          # STUB — empty; intended pydantic-settings config
│       ├── api/__init__.py    # STUB — empty; route registration here
│       ├── core/
│       │   ├── database.py    # STUB — empty; SQLAlchemy async engine here
│       │   ├── neo4j_client.py# STUB — empty; Neo4jClient class referenced by agent
│       │   ├── llm_client.py  # STUB — empty; get_llm() referenced by agent + extractor
│       │   └── exceptions.py  # ✓ Custom HTTP exceptions
│       ├── models/
│       │   ├── db_models.py   # ✓ SQLAlchemy: Document, ChatSession, ChatMessage
│       │   ├── schemas.py     # ✓ Pydantic API: Upload/Chat/Graph DTOs
│       │   └── entity_schemas.py # ✓ Duplicate of pipeline/extraction/schemas.py with Vietnamese annotations + ResolutionCandidate
│       ├── workers/__init__.py# STUB — empty; Celery app instance referenced by docker-compose
│       ├── security/__init__.py # STUB — empty; Presidio/slowapi wiring expected
│       └── services/__init__.py # STUB — empty
│
└── tests/
    └── test_week1.py          # ✓ 14 acceptance tests for "Week 1" scaffolding contract
```

**Directories referenced but missing on disk** (verified by `find`): `frontend/`, `infra/` (referenced in `docker-compose.yml:15,114`), `data/` (referenced in `docker-compose.yml:73,90` and `Makefile:24`), `backend/Dockerfile` (referenced in `docker-compose.yml:60,80`).

---

## 6. Tech Stack & Why

| Layer | Choice | Rationale (per `docs/architecture.md:67-77`) |
|---|---|---|
| Graph DB | **Neo4j Community 5** + APOC | Industry standard for property graphs; APOC for batch ops |
| Relational DB | **PostgreSQL 15 (asyncpg)** | Metadata, chat history; async driver matches FastAPI |
| Backend | **FastAPI** | Async-native, auto-generated OpenAPI |
| Agent | **LangGraph** | Cyclic graph supports multi-step reasoning loops |
| LLM | **Groq (Llama 3.3 70B versatile)** | Free tier, low latency |
| LLM (alt) | **Ollama (llama3.1:8b)** | Local/offline demo path |
| Structured output | **`instructor`** | Pydantic-typed LLM responses without manual JSON parsing |
| PDF parsing | **PyMuPDF (`fitz`)** | Handles 2-column layouts, tables, free |
| Task queue | **Celery + Redis** | Background processing for slow PDF/LLM jobs |
| Frontend (planned) | **Next.js + react-force-graph** | SSR + interactive graph visualization |
| Proxy | **Nginx** | Reverse proxy with WebSocket pass-through |
| PII | **Presidio** | Analyzer + anonymizer for input/output scrubbing |
| Rate limiting | **`slowapi`** | FastAPI-friendly rate limit decorator |
| File typing | **`python-magic`** | Magic-byte upload validation |

---

## 7. Service Topology (Docker Compose)

`docker-compose.yml` defines 7 services:

| Service | Image / Build | Ports | Purpose | Build status |
|---|---|---|---|---|
| `neo4j` | `neo4j:5-community` | 7474 (UI), 7687 (Bolt) | Knowledge graph | works once init script exists |
| `postgres` | `postgres:15-alpine` | 5432 | Document metadata, chat sessions | works |
| `redis` | `redis:7-alpine` | 6379 | Celery broker | works |
| `backend` | `./backend/Dockerfile` | 8000 | FastAPI app | **broken — Dockerfile missing** |
| `celery-worker` | `./backend/Dockerfile` | — | Runs `celery -A app.workers.celery_app worker` | **broken — Dockerfile missing, target module empty** |
| `frontend` | `./frontend/Dockerfile` | 3000 | Next.js UI | **broken — entire `frontend/` dir missing** |
| `nginx` | `nginx:1.27-alpine` | 80 | Reverse proxy | **broken — `infra/nginx/nginx.conf` missing** |

Volume mounts of note: `./infra/scripts/init_neo4j.cypher` is mounted into Neo4j's import dir (file doesn't exist yet); `./data` and a named `upload_data` volume are bind-mounted into backend & worker for shared file access.

Healthchecks defined for `neo4j`, `postgres`, `redis`. `backend`, `celery-worker` use `depends_on` with `service_healthy` so they wait for DBs.

---

## 8. Data Models

### 8.1 PostgreSQL (`backend/app/models/db_models.py`)

```python
class Document(Base):                   # __tablename__ = "documents"
    id              : str (UUID, PK)
    filename        : str(255)
    original_path   : str(500), nullable
    status          : str(20)  # "processing" | "completed" | "failed"
    entity_count    : int      = 0
    relation_count  : int      = 0
    error_message   : Text, nullable
    uploaded_at     : DateTime (UTC)
    completed_at    : DateTime, nullable

class ChatSession(Base):                # __tablename__ = "chat_sessions"
    id              : str (UUID, PK)
    created_at      : DateTime (UTC)

class ChatMessage(Base):                # __tablename__ = "chat_messages"
    id              : str (UUID, PK)
    session_id      : str (indexed)     # FK by convention; not enforced
    role            : str(20)           # "user" | "assistant"
    content         : Text
    reasoning_steps : Text, nullable    # JSON-serialized list[str]
    created_at      : DateTime (UTC)
```

Note: `Alembic` is in deps (`backend/requirements.txt:13`) but **no `alembic/` directory or migrations exist**. Schema must currently be created via `Base.metadata.create_all()` once `database.py` is implemented.

### 8.2 Neo4j Graph Schema (`docs/graph_schema.md`)

**Nodes** — all share `name` (unique key), `description`:

| Label | Extra props | Example |
|---|---|---|
| `Paper` | `year`, `abstract`, `keywords` | "Attention Is All You Need" |
| `Author` | `affiliation` | "Vaswani" |
| `Method` | — | "Transformer", "BERT" |
| `Metric` | `value` | "BLEU", "F1-score" |
| `Dataset` | `size` | "SQuAD", "ImageNet" |
| `Task` | — | "NER", "Machine Translation" |
| `Organization` | — | "Google", "OpenAI" |

**Edges** (all directed):

| Relation | Source → Target |
|---|---|
| `AUTHORED_BY` | Paper → Author |
| `CITES` | Paper → Paper |
| `USES_METHOD` | Paper → Method |
| `ACHIEVES_METRIC` | Paper → Metric |
| `EVALUATED_ON` | Paper → Dataset |
| `ADDRESSES_TASK` | Paper → Task |
| `BELONGS_TO` | Author → Organization |
| `IMPROVES` | Method → Method |
| `COMPARED_WITH` | Method → Method |

**Constraints / indexes** declared in docs (must be applied at init):

```cypher
CREATE CONSTRAINT FOR (p:Paper)  REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT FOR (a:Author) REQUIRE a.name IS UNIQUE;
CREATE CONSTRAINT FOR (m:Method) REQUIRE m.name IS UNIQUE;
CREATE INDEX      FOR (p:Paper)  ON (p.year);
```

These must live in `infra/scripts/init_neo4j.cypher` (mounted into the Neo4j container at startup) — file doesn't exist yet.

### 8.3 Pydantic API DTOs (`backend/app/models/schemas.py`)

```python
UploadResponse:        document_id, filename, status, message
ChatRequest:           message (1..2000 chars), session_id?
ChatResponse:          answer, sources[], reasoning_steps[], graph_data?
GraphNode:             id, label, type, properties{}
GraphEdge:             source, target, relation, properties{}
GraphData:             nodes[GraphNode], edges[GraphEdge]
DocumentInfo:          id, filename, status, uploaded_at, entity_count, relation_count
DocumentListResponse:  documents[DocumentInfo], total
```

### 8.4 Extraction schemas (`pipeline/extraction/schemas.py`)

Used as `response_model=` for `instructor` calls — these *are* the LLM's typed output contract:

```python
Entity:             name, type ∈ {Paper|Author|Method|Metric|Dataset|Task|Organization}, description
Relation:           source, target, relation ∈ {CITES|USES_METHOD|ACHIEVES_METRIC|AUTHORED_BY|EVALUATED_ON|BELONGS_TO|IMPROVES|COMPARED_WITH}, evidence
ExtractionResult:   entities[Entity], relations[Relation]
PaperMetadata:      title, authors[str], year?, abstract, keywords[]
```

There's a **near-duplicate** at `backend/app/models/entity_schemas.py` with the same fields plus a `ResolutionCandidate` model for entity dedup. Both should probably converge — currently they exist in parallel and either can be imported. See §17 *Open Questions* #2.

---

## 9. Pipeline Flow (Document Ingestion)

Implemented end-to-end except for the resolution & loader steps. Source-of-truth files:

### 9.1 PDF parsing (`pipeline/ingestion/pdf_parser.py`)

```python
parse_pdf(file_path) -> {
    "full_text": str,                                # whole doc, normalized
    "pages":     [{"page_num": int, "text": str}],
    "metadata":  {"title", "author", "subject", "creator"},  # from PDF metadata
    "num_pages": int,
}
```

Notable:
- `page.get_text("text", sort=True)` — `sort=True` reads 2-column layouts in correct order (`pdf_parser.py:29`).
- `_clean_page_text` drops standalone page numbers (≤4 digits) and lines <3 chars.
- `_normalize_text` does NFKC normalization and fixes hyphenated line breaks: `"trans-\nformer" → "transformer"` (`pdf_parser.py:75`).

```python
split_into_sections(text) -> [{"heading": str, "content": str}]
```

Regex `(?:^|\n)((?:\d+\.?\d*\.?\s+)?[A-Z][A-Za-z\s]{2,50})\n` captures headings like "1. Introduction" or "2.1 Method". Falls back to a single "Full Document" section if no headings detected.

### 9.2 Entity extraction (`pipeline/extraction/entity_extractor.py`)

```python
extract_entities_from_text(text, section_heading="", llm=None) -> ExtractionResult
extract_paper_metadata    (text,                     llm=None) -> PaperMetadata
```

Both use `instructor.from_langchain(llm)` to wrap the LangChain LLM and force a Pydantic-typed JSON response (`entity_extractor.py:24-32`). The `llm=None` default lazy-imports `from backend.app.core.llm_client import get_llm` — **this currently fails at runtime** because that file is empty.

**Prompts** (Vietnamese, `pipeline/extraction/prompts.py`):
- `EXTRACTION_PROMPT` — instructs LLM to NOT chunk, use consistent entity names, attach `evidence` to every relation, refuse uncertain extractions.
- `METADATA_PROMPT` — extract title/authors/year/abstract/keywords from front matter.

### 9.3 Image / vision (optional)

`pipeline/ingestion/image_extractor.py` extracts embedded images via PyMuPDF and can call a Vision-capable LLM for figure captioning. Implementation present but its caller hasn't been wired into the main pipeline yet.

### 9.4 Steps that are missing / empty

| Step | Where it should live | Status |
|---|---|---|
| Entity resolution (fuzzy + LLM verify) | `pipeline/resolution/` | empty dir |
| Bulk MERGE into Neo4j | `pipeline/loader/` | empty dir |
| Pipeline orchestrator (`run_pipeline.py`) | project root, called by `make seed` | **does not exist** |

---

## 10. Agent Flow (LangGraph)

### 10.1 State (`agent/state.py`)

```python
class AgentState(TypedDict):
    messages          : Annotated[list, add_messages]   # accumulating chat history
    user_query        : str                             # original question
    plan              : list[str]                       # planner output, numbered steps
    current_step      : int                             # router pointer
    retrieved_context : list[dict]                      # accumulated graph results
    final_answer      : str                             # synthesizer output
    graph_data        : dict                            # for frontend visualization
    needs_more_info   : bool                            # placeholder; not yet read by router
```

### 10.2 Graph topology (`agent/graph.py:30-55`)

```
              ┌─────────┐
              │  plan   │   plan_steps()       — LLM produces numbered plan
              └────┬────┘
                   ▼
              ┌─────────┐
       ┌─────►│retrieve │   retrieve_from_graph() — LLM → Cypher → Neo4j
       │      └────┬────┘
       │           │ should_continue(state)
       │           ▼
       │   current_step < len(plan)?
       │      yes ── loop ──┘
       │      no
       │           ▼
       │      ┌─────────┐
       └──────│synth.   │   synthesize_answer() — final markdown answer
              └────┬────┘
                   ▼
                  END
```

Router logic at `agent/graph.py:20-27`:

```python
def should_continue(state):
    return "retrieve" if state.get("current_step", 0) < len(state.get("plan", [])) else "synthesize"
```

### 10.3 Node responsibilities

| Node | File | LLM call | Reads | Writes |
|---|---|---|---|---|
| `plan` | `agent/nodes/planner.py` | `llm.invoke([SystemMessage(PLANNER_PROMPT), HumanMessage(query)])` | `user_query` | `plan`, `current_step=0`, `messages` |
| `retrieve` | `agent/nodes/retriever.py` | LLM → Cypher; `Neo4jClient.execute_query(cypher)` | `plan[current_step]` | `retrieved_context` (append), `current_step += 1` |
| `synthesize` | `agent/nodes/synthesizer.py` | `llm.invoke([...])` over context | `user_query`, `plan`, `retrieved_context` | `final_answer`, `messages` |

### 10.4 Public entry point

```python
async def run_agent(user_query: str) -> {"answer", "reasoning_steps", "graph_data"}
```
Compiles graph once at import (`agent/graph.py:59`), invokes via `agent_executor.ainvoke(initial_state)`.

### 10.5 Critical runtime dependency gap

Every node imports from `backend.app.core.llm_client` and `backend.app.core.neo4j_client`. **Both files are empty**, so the agent compiles successfully (the test `test_langgraph_graph_compile` passes because compilation only inspects structure) but **explodes at first invocation** with `ImportError: cannot import name 'get_llm'` or `'Neo4jClient'`.

---

## 11. API Surface (Inferred — not yet implemented)

Based on the Pydantic schemas and architecture diagram, the FastAPI app will expose roughly:

| Method | Path | Body / Params | Response | Status |
|---|---|---|---|---|
| `POST` | `/upload` | multipart PDF file | `UploadResponse` | not implemented |
| `GET` | `/documents` | — | `DocumentListResponse` | not implemented |
| `GET` | `/documents/{id}` | — | `DocumentInfo` | not implemented |
| `POST` | `/chat` | `ChatRequest` | `ChatResponse` | not implemented |
| `WS` | `/ws/chat` | streaming question/answer | streaming events | not implemented |
| `GET` | `/docs` (Swagger), `/openapi.json` | — | auto-generated by FastAPI | will work once `main.py` exists |

Routes will register through `backend/app/api/__init__.py`. The Swagger URL `http://localhost:8000/docs` is advertised in `README.md:74`.

---

## 12. Environment Variables (`.env.example`)

| Var | Default / example | Notes |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` \| `ollama` |
| `GROQ_API_KEY` | `gsk_your_key_here` | Required when `LLM_PROVIDER=groq` |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | When `LLM_PROVIDER=ollama` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` (Groq) or `llama3.1:8b` (Ollama) | Model name string |
| `NEO4J_URI` | `bolt://neo4j:7687` | Container DNS name |
| `NEO4J_USER` | `neo4j` | |
| `NEO4J_PASSWORD` | `graphrag_secret_2024` | Also referenced from compose default |
| `POSTGRES_USER` | `postgres` | |
| `POSTGRES_PASSWORD` | `postgres_secret_2024` | |
| `POSTGRES_DB` | `graphrag` | |
| `POSTGRES_URL` | `postgresql+asyncpg://postgres:postgres_secret_2024@postgres:5432/graphrag` | Async driver URL — used by SQLAlchemy |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker |
| `BACKEND_HOST` | `0.0.0.0` | |
| `BACKEND_PORT` | `8000` | |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:80"]` | JSON array |
| `UPLOAD_DIR` | `/app/data/uploads` | Inside container |
| `MAX_UPLOAD_SIZE_MB` | `50` | |

---

## 13. Run / Dev Commands

From `Makefile`:

```bash
make dev          # docker compose up --build         (full stack — currently fails: missing Dockerfiles)
make stop         # docker compose down
make dev-backend  # cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
                  # (currently fails — main.py is empty)
make dev-frontend # cd frontend && npm run dev        (currently fails — no frontend dir)
make test         # cd backend && python -m pytest tests/ -v
                  # (will fail — tests/ lives at repo root, not backend/tests/)
make seed         # cd pipeline && python run_pipeline.py --input ../data/sample_papers/
                  # (currently fails — run_pipeline.py + data/ don't exist)
make lint         # ruff check . --fix                across backend/, pipeline/, agent/
make clean        # docker compose down -v --rmi local && remove __pycache__
```

To actually run the working portion of the codebase right now:

```bash
# 1. Tests (acceptance suite — passes if 'Đề tài.pdf' exists at project root)
python tests/test_week1.py

# 2. PDF parsing standalone (no LLM)
python -c "from pipeline.ingestion.pdf_parser import parse_pdf; \
           print(parse_pdf('Đề tài.pdf')['num_pages'])"

# 3. Compile + structure-check the agent graph (no LLM call)
python -c "from agent.graph import build_agent_graph; print(build_agent_graph().get_graph().nodes)"
```

Anything that *invokes* an LLM or Neo4j currently dies on the empty `backend/app/core/*` modules.

---

## 14. Implementation Status

### ✅ Implemented (code present, syntactically valid, used by tests)

- `pipeline/ingestion/pdf_parser.py` — full
- `pipeline/ingestion/image_extractor.py` — full
- `pipeline/extraction/{schemas,prompts,entity_extractor}.py` — full (extractor depends on stubbed `llm_client`)
- `agent/{graph,state}.py` — full
- `agent/nodes/{planner,retriever,synthesizer}.py` — full (all depend on stubbed `llm_client` / `neo4j_client`)
- `backend/app/models/{db_models,schemas,entity_schemas}.py` — full
- `backend/app/core/exceptions.py` — full
- `tests/test_week1.py` — 14 acceptance tests
- `docs/{architecture,graph_schema}.md` — full (Vietnamese)

### ⚠️ Stubbed (file or dir exists but empty / no code)

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/core/database.py`
- `backend/app/core/neo4j_client.py`
- `backend/app/core/llm_client.py`
- `backend/app/api/__init__.py`
- `backend/app/workers/__init__.py`     ← Celery app referenced in `docker-compose.yml:82`
- `backend/app/security/__init__.py`
- `backend/app/services/__init__.py`
- `agent/tools/__init__.py`
- `pipeline/loader/__init__.py`
- `pipeline/resolution/__init__.py`
- `pipeline/__init__.py`, all subpackage `__init__.py`s

### ❌ Missing entirely (referenced but not on disk)

- `frontend/` — entire Next.js app (compose file builds from `./frontend/Dockerfile`)
- `infra/` — Nginx config (`infra/nginx/nginx.conf`), Neo4j init script (`infra/scripts/init_neo4j.cypher`)
- `data/` — sample papers dir, upload bind-mount target
- `backend/Dockerfile` — required by `backend` and `celery-worker` services
- `frontend/Dockerfile` — required by `frontend` service
- `backend/tests/` — `make test` `cd`s into `backend/` first; current tests live at repo root
- `pipeline/run_pipeline.py` — `make seed` calls this
- Alembic migration tree

---

## 15. Test Suite

`tests/test_week1.py` — 14 standalone tests (manual `try/except` style, not pytest discovery), divided into two role-based groups:

### Team Leader contract

| # | What it asserts | Source |
|---|---|---|
| 1 | Top-level dirs exist: `agent/`, `pipeline/`, `backend/`, `docs/`, `data/`, `infra/` | `test_week1.py:36-42` |
| 2 | `docs/architecture.md` >500 chars and mentions FastAPI / Neo4j / LangGraph | `:45-54` |
| 3 | `docs/graph_schema.md` includes Paper/Author/Method/Metric/Dataset and CITES/USES_METHOD/AUTHORED_BY/ACHIEVES_METRIC | `:57-68` |
| 4a | Imports `langgraph.graph.StateGraph` and `agent.state.AgentState` with required fields | `:71-78` |
| 4b | Imports the three node functions and confirms they're callable | `:81-88` |
| 4c | `build_agent_graph()` compiles and graph has nodes `plan`/`retrieve`/`synthesize` | `:91-101` |

### Data Engineer contract

| # | What it asserts | Source |
|---|---|---|
| 5a | Imports `parse_pdf`, `split_into_sections` | `:109-114` |
| 5b | Parses real `Đề tài.pdf` at project root (>100 chars, ≥1 page, ≥1 section) | `:116-143` |
| 6a | Pydantic schemas instantiate, serialize to JSON correctly | `:146-170` |
| 6b | `EXTRACTION_PROMPT` >100 chars, contains `CITES`, `USES_METHOD`, mentions chunking | `:173-180` |
| 6c | Entity extractor functions importable | `:183-187` |

Tests assert structural contracts of the scaffold — they do **not** call LLMs, Neo4j, Postgres, or Celery. Suite passes today (assuming `Đề tài.pdf` is at project root) — but tests `1` will fail because `data/` and `infra/` directories don't exist yet.

---

## 16. Implicit Conventions

Picked up from reading the code; preserve these when contributing:

1. **Bilingual code** — identifiers in English, comments and docstrings primarily in Vietnamese. Don't translate existing comments.
2. **Async everywhere** — FastAPI async routes, SQLAlchemy `[asyncio]` extras, `asyncpg`, `httpx`, `pytest-asyncio`. New blocking I/O should run through Celery.
3. **No plain-text chunking for extraction** — explicit rule (`pipeline/extraction/prompts.py:14`, `pipeline/extraction/schemas.py:6`). Extraction operates on whole sections.
4. **Pydantic for all LLM outputs** via `instructor` — never parse model JSON manually.
5. **Lazy LLM imports inside functions** (`from backend.app.core.llm_client import get_llm` inside the function body, not at module top) — avoids import cycles between `agent/` ↔ `pipeline/` ↔ `backend/`.
6. **UUIDs as strings** for primary keys (not `UUID` type) — see `Document.id` default.
7. **UTC timestamps** — `datetime.now(timezone.utc)` everywhere.
8. **Vietnamese prompts to the LLM** — model is expected to answer in Vietnamese (`SYNTHESIS_PROMPT` at `agent/nodes/synthesizer.py:11`).
9. **`Đề tài.pdf` = "Project Brief PDF"** — referenced in tests but kept out of git (likely the prof's spec sheet).

---

## 17. Inferred Team Roles

The Week-1 test file groups assertions by role (`tests/test_week1.py:31-104`). The team appears to be at minimum:

| Role | Scope | Files owned |
|---|---|---|
| Team Leader | Repo skeleton, architecture doc, graph schema, LangGraph wiring | `docs/`, `agent/` |
| Data Engineer ("Minh Khánh", credited in `backend/app/models/entity_schemas.py:5`) | PDF parsing, extraction prompts, Pydantic schemas | `pipeline/ingestion/`, `pipeline/extraction/` |
| **Backend Engineer** (probably the user) | FastAPI app, DB clients, Celery worker | `backend/app/main.py`, `core/`, `api/`, `workers/`, `services/` (all currently empty) |
| **Frontend Engineer** | Next.js UI, graph visualization | `frontend/` (doesn't exist yet) |
| **DevOps** | Dockerfiles, Nginx config, Neo4j init script | `infra/`, `backend/Dockerfile`, `frontend/Dockerfile` (all missing) |

The empty `__init__.py`s in `backend/app/{api,workers,security,services}` strongly suggest these are reserved for the backend engineer to fill in.

---

## 18. Open Questions for the Senior

1. **`llm_client.py` design** — should `get_llm()` be a cached factory keyed on `LLM_PROVIDER`? Should it return a LangChain `BaseChatModel` so `instructor.from_langchain(llm)` keeps working?
2. **Schema duplication** — `pipeline/extraction/schemas.py` vs `backend/app/models/entity_schemas.py` define almost identical models. Which one is canonical? Should the backend re-export from the pipeline?
3. **Celery app location** — `docker-compose.yml:82` references `app.workers.celery_app`. Is the Celery instance supposed to live in `backend/app/workers/celery_app.py`, or in `backend/app/workers/__init__.py`?
4. **Agent ↔ backend coupling** — `agent/nodes/*.py` import from `backend.app.core`. Is `agent/` meant to be importable standalone (via PYTHONPATH manipulation) or always run inside the backend container? If the latter, the import paths are fine; if standalone, `llm_client` and `neo4j_client` should move to `agent/clients/` or a shared `common/` package.
5. **Validator node** — the architecture diagram (`docs/architecture.md:25`) shows a Validator looping back to Retriever. The compiled graph doesn't include it. Defer to v2 or add now?
6. **Entity resolution** — `pipeline/resolution/` is empty. Is this scaffolded for a future sprint, or should the backend engineer drop fuzzy-match + LLM-verify code there before the loader runs?
7. **Frontend scaffold** — does it already live in another repo (and the team will `git submodule add` later), or does someone need to `npx create-next-app frontend/`?
8. **Tests location** — `Makefile:20` runs `cd backend && python -m pytest tests/`, but the test file lives at repo-root `tests/`. Move tests, or adjust the Makefile?
9. **Alembic migrations** — `alembic` is in `requirements.txt` but no `alembic.ini` or `migrations/`. Plan to introduce, or rely on `Base.metadata.create_all()` for now?
10. **`run_pipeline.py`** — `make seed` calls `pipeline/run_pipeline.py`. Should this be a Click/Typer CLI, an async Celery-bypassing script, or a thin wrapper that enqueues tasks?

---

## 19. Glossary

| Term | Meaning here |
|---|---|
| **GraphRAG** | RAG variant where retrieval is over a structured graph rather than vector-embedded text chunks |
| **Knowledge Graph** | Property graph in Neo4j with typed nodes (Paper/Author/...) and labeled edges (CITES/USES_METHOD/...) |
| **Entity Resolution** | Deduplication step that decides "Vaswani" and "Ashish Vaswani" are the same Author node |
| **Cypher** | Neo4j's declarative query language, equivalent to SQL for graphs |
| **`instructor`** | Python library that wraps an LLM call, validating output against a Pydantic schema (retries on schema mismatch) |
| **LangGraph StateGraph** | Cyclic directed graph of node functions; each transition produces a partial-state dict that's merged into the running `AgentState` |
| **Magic bytes** | First few bytes of a file used to identify its true type (`python-magic`) — used for upload validation |
| **Presidio** | Microsoft library for detecting and anonymizing PII (names, addresses, etc.) |
| **APOC** | Neo4j plugin "Awesome Procedures On Cypher" — utility procedures for batch ops, JSON parsing, etc. |
| **`Đề tài.pdf`** | Vietnamese for "Project topic.pdf" — the professor's project brief, referenced by tests but gitignored |

---

*Generated 2026-04-30 from a cold read of the repo. Verify any claim against the cited file paths before depending on it.*
