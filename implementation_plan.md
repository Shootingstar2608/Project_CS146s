# Hybrid Retrieval System: KG + Vector Embeddings

Extend the existing Graph-RAG agent (which already does KG-only retrieval via Neo4j + Cypher) into a **hybrid pipeline** that fuses dense semantic search (FAISS + SentenceTransformers) with the existing structured KG retrieval.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Embedding model**: Default plan is `all-MiniLM-L6-v2` from SentenceTransformers (fully local, no API key needed, 384-dim, fast). Acceptable? Or should it be OpenAI `text-embedding-3-small`?

> [!IMPORTANT]
> **Q2 — Chunking strategy**: The existing code has a `split_into_sections()` helper (section-level splits). The plan adds overlapping character chunking *inside* sections (chunk_size=512 tokens / overlap=64 tokens). OK?

> [!NOTE]
> **Q3 — FAISS persistence**: FAISS index will be saved to disk (`data/faiss/`) and loaded on startup. No Qdrant or external vector DB to keep it zero-dependency for local dev. Swap-in hooks are provided.

---

## Proposed Changes

### 1. New Dependencies

#### [MODIFY] [requirements.txt](file:///home/ducquan/Documents/Python/CS146/references/Project_CS146s/backend/requirements.txt)
Add:
- `sentence-transformers>=3.3` — local embedding model
- `faiss-cpu>=1.9` — vector index (GPU variant swap-in ready)
- `rank-bm25>=0.2.2` — lightweight BM25 for optional sparse re-ranking

---

### 2. Embedding Pipeline (new sub-package `pipeline/embedding/`)

```
pipeline/
  embedding/
    __init__.py
    chunker.py          # text → overlapping chunks with metadata
    embedder.py         # SentenceTransformers wrapper (swap-in OpenAI)
    vector_store.py     # FAISS index: build / save / load / search
    ingest.py           # orchestrator: PDF parse → chunk → embed → index
```

#### [NEW] `pipeline/embedding/chunker.py`
Splits section text into **fixed-size token-approximate chunks** with overlap.

- `chunk_size=512 chars`, `overlap=64 chars` (character-based for language agnosticism)
- Each `Chunk` carries: `chunk_id`, `paper_id`, `text`, `source_section`, `title`, `authors`, `year`

#### [NEW] `pipeline/embedding/embedder.py`
Thin wrapper around `SentenceTransformer("all-MiniLM-L6-v2")`.
- `embed_texts(texts) → np.ndarray`
- `embed_query(text) → np.ndarray`
- Lazy-loaded singleton to avoid repeated model init

#### [NEW] `pipeline/embedding/vector_store.py`
FAISS-based store:
- `build_index(embeddings, chunks)`
- `save(path)` / `load(path)` 
- `search(query_embedding, top_k=5) → list[Chunk]`
- Uses `IndexFlatIP` (inner product on L2-normalized vectors = cosine similarity)

#### [NEW] `pipeline/embedding/ingest.py`
Orchestrator called by the Celery worker after KG ingestion:
```
parse_pdf → split_into_sections → chunk_section → embed → add_to_index
```

---

### 3. Core Infrastructure

#### [MODIFY] `backend/app/core/neo4j_client.py` (currently empty)
Implement `Neo4jClient` with:
- `execute_query(cypher, params) → list[dict]`
- Connection pooling, timeout, graceful error

#### [MODIFY] `backend/app/core/llm_client.py` (currently empty)
Implement `get_llm()` factory:
- Reads `LLM_PROVIDER` from env (`groq` | `ollama`)
- Returns a LangChain chat model

#### [MODIFY] `backend/app/config.py` (currently empty)
`Settings` (pydantic-settings) for all env vars including new:
- `VECTOR_STORE_PATH=data/faiss`
- `EMBEDDING_MODEL=all-MiniLM-L6-v2`
- `HYBRID_ALPHA=0.5`  ← weight: 0=pure KG, 1=pure vector

---

### 4. Hybrid Retrieval Query Layer (new `pipeline/retrieval/`)

```
pipeline/
  retrieval/
    __init__.py
    query_router.py     # decide KG-heavy vs vector-heavy
    vector_retriever.py # query FAISS → top-k chunks
    graph_retriever.py  # extract entities → Cypher → Neo4j
    fusion.py           # RRF merge + format prompt context
    reranker.py         # (bonus) cross-encoder re-rank
```

#### [NEW] `pipeline/retrieval/query_router.py`
Heuristic + LLM-assisted router:
- **KG-heavy** when query contains named entity patterns (paper names, author names, method names, comparison keywords)
- **Vector-heavy** when query is broad/conceptual ("what are challenges in…")
- Returns `alpha` float in `[0, 1]` to weight fusion

#### [NEW] `pipeline/retrieval/vector_retriever.py`
```python
def retrieve_chunks(query: str, top_k: int = 5) -> list[RetrievedChunk]
```
Embeds query → FAISS search → returns ranked chunks with scores.

#### [NEW] `pipeline/retrieval/graph_retriever.py`
```python
def retrieve_from_graph(query: str, entities: list[str]) -> list[dict]
```
Wraps existing `retrieve_from_graph` logic; extracts named entities first, then generates focused Cypher.

#### [NEW] `pipeline/retrieval/fusion.py`
**Reciprocal Rank Fusion (RRF)**:
```
score(d) = Σ 1/(k + rank_i(d))   [k=60 constant]
```
Merges vector results and KG results into a unified ranked context block for the LLM prompt.

#### [NEW] `pipeline/retrieval/reranker.py` (bonus)
Optional `cross-encoder/ms-marco-MiniLM-L-6-v2` cross-encoder re-ranking of top-20 candidates → keep top-5.

---

### 5. Agent Upgrade

#### [MODIFY] [state.py](file:///home/ducquan/Documents/Python/CS146/references/Project_CS146s/agent/state.py)
Add fields:
- `vector_chunks: list[dict]` — raw retrieved chunks
- `retrieval_mode: str` — `"kg"` | `"vector"` | `"hybrid"`
- `alpha: float` — fusion weight used

#### [MODIFY] [retriever.py](file:///home/ducquan/Documents/Python/CS146/references/Project_CS146s/agent/nodes/retriever.py)
Replace KG-only logic with hybrid pipeline call:
1. Call `query_router` → get `alpha`
2. Call `vector_retriever` → top-k chunks
3. Call `graph_retriever` → KG facts
4. Call `fusion.fuse()` → merged context
5. Store both `vector_chunks` and `retrieved_context` in state

#### [MODIFY] [synthesizer.py](file:///home/ducquan/Documents/Python/CS146/references/Project_CS146s/agent/nodes/synthesizer.py)
Update prompt to include **both** semantic chunks and KG facts, and instruct LLM to cite paper titles from chunk metadata.

---

### 6. Backend Wiring

#### [MODIFY] `backend/app/main.py` (currently empty)
Minimal FastAPI app:
- `POST /api/query` → runs hybrid agent, returns answer + sources
- `POST /api/upload` → triggers Celery ingest task
- `GET /api/health`

#### [MODIFY] `backend/app/core/database.py` (currently empty)
SQLAlchemy async engine + session factory for PostgreSQL.

---

### 7. Docker / Config

#### [MODIFY] [.env.example](file:///home/ducquan/Documents/Python/CS146/references/Project_CS146s/.env.example)
Add new variables:
```
VECTOR_STORE_PATH=data/faiss
EMBEDDING_MODEL=all-MiniLM-L6-v2
HYBRID_ALPHA=0.5
RERANK_ENABLED=false
```

#### [MODIFY] [docker-compose.yml](file:///home/ducquan/Documents/Python/CS146/references/Project_CS146s/docker-compose.yml)
Add `data/faiss` to backend volume mounts.

---

### 8. Tests

#### [NEW] `tests/test_embedding_pipeline.py`
- Chunker output shape
- Embedder dimension check
- FAISS round-trip search

#### [NEW] `tests/test_hybrid_retrieval.py`
- `query_router` returns valid alpha
- `fusion` RRF correctness
- End-to-end `run_agent()` mock test

#### [NEW] `tests/test_example.py`
- Runnable example script demonstrating the full pipeline

---

## Architecture Diagram (After Change)

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────┐
│               LangGraph Agent                   │
│                                                 │
│  [Planner] → identifies query intent            │
│       │                                         │
│       ▼                                         │
│  [Hybrid Retriever]                             │
│    ├─ Query Router ──────────────────────────┐  │
│    │    (heuristic + LLM)   alpha ∈ [0,1]   │  │
│    │                                         │  │
│    ├─ Vector Retriever ──► FAISS Index       │  │
│    │    SentenceTransformers                 │  │
│    │    top-k chunks + metadata              │  │
│    │                                         │  │
│    ├─ Graph Retriever ──► Neo4j (Cypher)     │  │
│    │    entity extraction                    │  │
│    │    structured KG facts                  │  │
│    │                                         │  │
│    └─ RRF Fusion ◄──────────────────────────┘  │
│         (optional: CrossEncoder rerank)         │
│              │                                  │
│              ▼                                  │
│  [Synthesizer] ──► LLM (Groq/Ollama)           │
│    Prompt = KG facts + semantic chunks          │
│    → Answer with paper citations                │
└─────────────────────────────────────────────────┘
         │                    │
    Neo4j (KG)         FAISS (Vectors)
         │                    │
    PostgreSQL         data/faiss/*.index
    (Metadata)
```

---

## Verification Plan

### Automated Tests
```bash
pytest tests/test_embedding_pipeline.py -v
pytest tests/test_hybrid_retrieval.py -v
python tests/test_example.py  # full demo walkthrough
```

### Manual Verification
1. Upload a sample PDF → confirm chunks appear in FAISS index
2. Query "What methods does [paper] use?" → confirm KG results dominate (alpha low)
3. Query "What are challenges in neural machine translation?" → confirm vector chunks dominate
4. Check final answer cites paper titles from chunk metadata
