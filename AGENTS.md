# Project CS146s Agent Guide

This file is for coding agents joining the repository cold. It explains what the project is, what is implemented, how the system is intended to work, and the commands/gotchas needed to make safe changes.

## Project Purpose

Project CS146s is a local-demo GraphRAG research assistant for academic PDFs.

The app lets a user:

1. Upload PDF papers through a web UI.
2. Parse and index those papers in the backend.
3. Store document metadata in PostgreSQL.
4. Store paper entities and relationships in Neo4j.
5. Store text chunk embeddings in a FAISS vector index.
6. Ask questions in chat and receive answers grounded in graph/vector retrieval.
7. Browse uploaded papers and visualize the knowledge graph in the frontend.

The intended demo story is: upload a paper, wait for indexing, see it appear in the library/graph, then ask a question about it in chat.

## Current Implementation Status

The project is end-to-end functional for a local demo.

Implemented:

- Docker Compose stack for frontend, backend, Celery worker, Redis, PostgreSQL, Neo4j, and Nginx.
- FastAPI backend with upload, documents, files, graph, chat, health, and full-health endpoints.
- Celery ingestion worker with inline fallback if the queue is unavailable.
- PDF parsing with PyMuPDF.
- FAISS vector index with metadata sidecar files.
- Default deterministic hashing embedder so the demo can run without downloading model weights.
- Optional SentenceTransformer embedder if installed and configured.
- Neo4j paper/author/entity graph writes.
- LangGraph agent path for LLM-backed planning, retrieval, and synthesis.
- Local retrieval fallback for chat when no Groq/Ollama LLM is configured.
- Next.js frontend for papers, upload, chat, and graph views.

Not implemented or intentionally limited:

- Chat is REST POST, not WebSocket streaming.
- The validator loop mentioned in older docs is not implemented.
- There is no Alembic migration tree; SQLAlchemy creates current tables at startup.
- LLM quality depends on configuring Groq or Ollama. Without an LLM, chat returns an extractive local retrieval fallback.
- Presidio and slowapi are not part of the current runtime despite older README wording.

## Architecture

```text
Frontend (Next.js)
  pages: /papers, /papers/[id], /upload, /chat, /graph
  talks to backend through REST API

Backend (FastAPI)
  validates uploads
  stores document rows in PostgreSQL
  serves documents, PDFs, graph data, and chat responses
  dispatches ingestion to Celery

Celery Worker
  parses PDFs
  extracts or heuristically infers metadata
  chunks text
  embeds chunks
  saves FAISS index
  writes graph records to Neo4j

Data Layer
  PostgreSQL: document metadata/status
  Neo4j: knowledge graph nodes/edges
  FAISS: vector index and chunk metadata
  Redis: Celery broker/result backend

Agent
  LangGraph plan -> retrieve loop -> synthesize
  retrieval combines graph and vector paths when LLM is configured
  local retrieval fallback is used when the configured LLM is unavailable
```

## Important Paths

- `docker-compose.yml`: full local stack.
- `Makefile`: common commands.
- `backend/app/main.py`: FastAPI app, lifespan startup, health endpoints, router registration.
- `backend/app/config.py`: environment-backed settings.
- `backend/app/api/upload.py`: PDF upload and ingestion dispatch.
- `backend/app/api/router_chat.py`: chat endpoint.
- `backend/app/api/router_documents.py`: uploaded paper list.
- `backend/app/api/router_graph.py`: graph and per-paper subgraph endpoints.
- `backend/app/api/router_files.py`: PDF download endpoint.
- `backend/app/core/database.py`: PostgreSQL setup.
- `backend/app/core/neo4j_client.py`: Neo4j query helpers.
- `backend/app/core/llm_client.py`: Groq/Ollama LangChain model factory.
- `backend/app/workers/celery_app.py`: Celery app and ingestion task.
- `pipeline/embedding/ingest.py`: main PDF ingestion orchestrator.
- `pipeline/embedding/embedder.py`: hashing and optional SentenceTransformer embedders.
- `pipeline/embedding/vector_store.py`: FAISS persistence.
- `pipeline/retrieval/vector_retriever.py`: vector search.
- `pipeline/retrieval/graph_retriever.py`: graph retrieval.
- `pipeline/retrieval/fusion.py`: retrieval result fusion.
- `pipeline/extraction/`: extraction schemas, prompts, and LLM extraction.
- `pipeline/loader/neo4j_loader.py`: Neo4j graph loading helpers.
- `agent/graph.py`: LangGraph setup and local fallback.
- `agent/nodes/`: planner, retriever, synthesizer nodes.
- `frontend/AGENTS.md`: frontend-specific Next.js warning and guidance.
- `frontend/src/lib/api.ts`: axios client and backend API helpers.
- `frontend/src/lib/research-store.ts`: persisted client-side chat/session state.
- `docs/architecture.md`: architecture notes.
- `docs/graph_schema.md`: intended graph schema.

## Local Run

Recommended full-stack run:

```bash
docker compose up --build -d
```

Useful URLs:

- Frontend: `http://localhost:3000`
- Nginx entry: `http://localhost`
- Backend health: `http://localhost:8000/health`
- Full backend health: `http://localhost:8000/health/full`
- Backend docs: `http://localhost:8000/docs`
- Neo4j Browser: `http://localhost:7474`

Stop:

```bash
docker compose down
```

Reset local DB/upload data:

```bash
make reset-db
```

## Environment

Copy `.env.example` to `.env` for local configuration.

Key settings:

- `LLM_PROVIDER=groq` with `GROQ_API_KEY=...` for Groq.
- `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=...`, and `LLM_MODEL=...` for local Ollama.
- If no LLM is configured, chat should still return a local retrieval fallback instead of failing.
- `EMBEDDING_MODEL` defaults to `hashing` in code. Use a non-hashing model name only if `sentence-transformers` is installed and model download/runtime cost is acceptable.
- `FAISS_INDEX_PATH` defaults to `/app/data/faiss_index` inside Docker.
- `UPLOAD_DIR` defaults to `/app/data/uploads` inside Docker.

## Main API Surface

- `GET /health`: lightweight backend health.
- `GET /health/full`: checks PostgreSQL and Neo4j.
- `POST /api/v1/upload/`: upload PDF and start ingestion.
- `GET /api/v1/documents`: list indexed/uploaded documents.
- `GET /api/v1/files/{document_id}/pdf`: download original uploaded PDF.
- `GET /api/v1/graph`: graph visualization data.
- `GET /api/v1/graph/paper/{paper_id}`: subgraph around one paper.
- `POST /api/v1/chat/`: ask a question.

## Verification Commands

Run these before claiming a backend/runtime change is safe:

```bash
python -m compileall agent backend/app pipeline -q
python -m pytest tests/ -q
docker compose config --quiet
git diff --check
```

Run these before claiming a frontend change is safe:

```bash
cd frontend
npm run lint
npm run build
```

Run these for demo-readiness verification:

```bash
docker compose up --build -d
curl -sS http://localhost:8000/health/full
curl -sS http://localhost:8000/api/v1/documents
curl -sS http://localhost:8000/api/v1/graph
curl -sS -X POST http://localhost:8000/api/v1/chat/ \
  -H 'Content-Type: application/json' \
  -d '{"message":"What does the uploaded paper discuss?","top_k":3}'
```

## Data And Git Hygiene

- Treat `data/uploads/` and `data/faiss_index/` as runtime/demo data unless the task explicitly asks to seed demo data.
- Do not casually commit generated FAISS changes; they can change after uploads.
- Do not commit local logs or assistant-specific files such as `.claude/claudex/log`.
- The worktree may contain user changes. Do not revert or stage unrelated files.
- Main is protected on GitHub. Push work to a feature branch and open a PR.

## Coding Guidance For Future Agents

- Prefer existing patterns over new abstractions.
- Keep backend imports compatible with Docker `PYTHONPATH=/app/backend:/app`.
- Preserve the REST API shape expected by `frontend/src/lib/api.ts`.
- Keep chat resilient when no external LLM key is present.
- Keep upload validation strict: PDF extension, MIME, magic bytes, and size limit.
- Keep ingestion asynchronous through Celery, with inline fallback only as a resilience path.
- When touching retrieval, verify both empty-index behavior and indexed-document behavior.
- When touching graph code, test both `/api/v1/graph` and `/api/v1/graph/paper/{paper_id}`.
- When touching frontend, read `frontend/AGENTS.md`; this repo uses Next.js 16, which may differ from older assumptions.
- Use concise comments only where they clarify non-obvious behavior.

## Known Demo Behavior

- Fresh uploads should appear as `processing` first, then `indexed` after ingestion completes.
- If no LLM key is configured, metadata extraction falls back to simple heuristics from the PDF text.
- If no LLM key is configured, chat returns an answer that explicitly says it used local GraphRAG retrieval fallback.
- Graph quality improves when LLM extraction is configured; without it, the graph may contain only paper/author metadata and heuristic entities.
