# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repo. Keep it accurate — update it when the architecture or commands change.

## What this is

**Project CS146s** is a **Hybrid GraphRAG** research assistant. It ingests academic PDFs, builds a Neo4j knowledge graph of papers/authors/methods/metrics/datasets, indexes chunk embeddings in FAISS, and answers questions with a multi-step **LangGraph** agent that fuses graph (Cypher) and vector retrieval before an LLM synthesizes a cited answer.

Stack: **FastAPI** (async) backend, **Next.js 16** frontend, **Neo4j 5 + APOC**, **PostgreSQL 15** (asyncpg), **Celery + Redis** workers, **Groq** (Llama 3.3 70B) or **Ollama** as the LLM, **FAISS** for vectors. Everything runs under Docker Compose.

## Layout

```
agent/        LangGraph agent: graph.py (Plan→Retrieve loop→Synthesize), state.py, nodes/
pipeline/     Ingestion + retrieval, importable standalone
  ingestion/  pdf_parser.py (PyMuPDF, 2-column aware), image_extractor.py
  extraction/ schemas.py, prompts.py, entity_extractor.py (instructor + LLM, typed output)
  embedding/  chunker, embedder, vector_store (FAISS), ingest.py (end-to-end seed)
  retrieval/  vector_retriever, graph_retriever, fusion (RRF + alpha), reranker, query_router
  loader/     neo4j_loader.py (bulk MERGE into the graph)
backend/app/  FastAPI service
  main.py     entrypoint (lifespan, CORS, routers, /health)
  config.py   pydantic-settings (get_settings, lru_cached)
  api/        routers: upload, router_chat, router_documents, router_graph, router_files
  core/       database.py (async SQLAlchemy), neo4j_client.py, llm_client.py, exceptions.py
  models/     db_models.py (SQLAlchemy), schemas.py (API DTOs), entity_schemas.py
  security/   prompt_guard.py, sanitizer.py
  workers/    celery_app.py
frontend/     Next.js 16 / React 19 / Tailwind 4 app (src/app, src/lib/api.ts is the API client)
infra/        nginx config, Neo4j init cypher
docs/         architecture.md, graph_schema.md (Vietnamese, authoritative for the graph model)
data/         faiss_index/ (committed demo index), uploads/
tests/        test_week1.py (scaffold acceptance suite)
```

## Commands

```bash
make dev            # docker compose up --build (full stack)
make stop           # docker compose down
make dev-backend    # uvicorn app.main:app --reload  (run from backend/; needs PYTHONPATH — see below)
make dev-frontend   # cd frontend && npm run dev
make test           # python -m pytest tests/ -v
make seed           # ingest data/sample_papers into FAISS + Neo4j (pipeline.embedding.ingest)
make lint           # ruff check --fix across backend/, pipeline/, agent/
make reset-db       # wipe Neo4j + Postgres + uploads, keep containers
```

Services once up: frontend `:3000`, backend `:8000` (Swagger at `/docs`), Neo4j UI `:7474` (Bolt `:7687`), Postgres host `:5433` → container `5432`, Redis `:6379`.

## The import-path gotcha (read before running anything outside Docker)

Modules use **two** import roots, mixed across the codebase:
- `from app.config import ...`, `from app.core.llm_client import ...` → resolves only when **`backend/`** is on `PYTHONPATH`.
- `from backend.app.core... import ...`, `from agent...`, `from pipeline...` → resolves only when the **repo root** is on `PYTHONPATH`.

So **both** must be on the path simultaneously. Docker sets `PYTHONPATH=/app/backend:/app` (see `backend/Dockerfile`). For local runs do the equivalent from the repo root:

```bash
PYTHONPATH=backend:. python -m pytest tests/ -v
PYTHONPATH=backend:. python -c "from pipeline.embedding.ingest import ingest_directory; ingest_directory('data/sample_papers')"
```

Imports of `app.*`/`backend.app.*` are done **lazily inside functions** (not at module top) to avoid `agent ↔ pipeline ↔ backend` import cycles. Preserve that pattern.

## Conventions (match these)

- **Bilingual code**: identifiers in English; comments, docstrings, and LLM prompts are mostly **Vietnamese**. Don't translate existing Vietnamese — keep new comments consistent with the file.
- **Async everywhere** in the backend (FastAPI routes, async SQLAlchemy, asyncpg). `Neo4jClient.execute_query` is **synchronous** — it's called directly from async code; keep Neo4j calls quick or offload heavy work to Celery.
- **No plain-text chunking for entity extraction** — extraction runs section-by-section and emits typed entities directly (`pipeline/extraction/prompts.py`, `schemas.py`). Chunking (`pipeline/embedding/chunker.py`) is only for the vector index.
- **All LLM outputs are Pydantic-typed via `instructor`** — never hand-parse model JSON.
- **Hybrid retrieval** = Reciprocal Rank Fusion of vector + KG results with an `alpha` weight (0=graph-only, 1=vector-only, default 0.5) in `pipeline/retrieval/fusion.py`. The `/chat` request can override `alpha` and `top_k`.
- **Demo-friendly defaults**: `EMBEDDING_MODEL=hashing` uses a deterministic bag-of-words embedder so the stack runs without downloading ML models. Switch to a real `sentence-transformers` model by setting `EMBEDDING_MODEL` to its name. A committed FAISS index lives in `data/faiss_index/`.
- **LLM fallback**: if `GROQ_API_KEY` is unset (or the provider is unreachable), `agent/graph.py` falls back to a local vector-retrieval-only answer instead of erroring. Full agent reasoning needs a configured LLM provider.
- **UUID string PKs**, **UTC timestamps** (`datetime.now(timezone.utc)`), settings via `get_settings()`.

## Config

Copy `.env.example` → `.env`. Key vars: `LLM_PROVIDER` (`groq`|`ollama`), `GROQ_API_KEY`, `LLM_MODEL`, `NEO4J_*`, `POSTGRES_URL`, `REDIS_URL`, `EMBEDDING_MODEL`, `FAISS_INDEX_PATH`, `UPLOAD_DIR`. Compose has safe defaults for infra, but ingestion/chat need a real LLM key to be fully functional.

## When changing things

- **Graph schema** (node/edge types): `docs/graph_schema.md` is the reference; the live label/relation sets also appear in `agent/nodes/retriever.py` (`CYPHER_PROMPT`) and `pipeline/loader/neo4j_loader.py`. Keep them in sync.
- **API ↔ frontend contract**: backend DTOs in `backend/app/models/schemas.py`; the frontend axios client is `frontend/src/lib/api.ts` (base URL `NEXT_PUBLIC_API_URL`, default `http://localhost:8000/api/v1`), and data fetching goes through TanStack React Query hooks in `frontend/src/lib/queries.ts` (`useDocuments`, `useGraph`, `useDeleteDocument`) — mutate the cache via these and invalidate `['documents']`/`['graph']` rather than refetching ad hoc.
- **FAISS writes** (ingest add, document delete) must hold `vector_store_lock` from `pipeline/embedding/vector_store.py` — the flat index + parallel metadata list are not concurrency-safe.
- **Frontend** is Next.js 16 — see `frontend/AGENTS.md`: APIs may differ from older Next.js; check `node_modules/next/dist/docs/` before writing framework code.

## Deeper docs

- `docs/architecture.md`, `docs/graph_schema.md` — design + graph model (Vietnamese).
- `ONBOARDING.md` — long-form cold-start guide, refreshed 2026-06-04 to match the current code (backend, frontend, hybrid retrieval, FAISS, local fallback). Still verify any claim against the cited file paths before depending on it.

(`AGENTS.md` at the repo root is the **user's** personal context profile, not repo instructions.)
