"""
End-to-End Demo Script: Hybrid Retrieval System

This script demonstrates the full pipeline with a synthetic example:
  1. Create sample text (mimicking parsed PDF sections)
  2. Chunk, embed, and index the text into FAISS
  3. Run a hybrid query (vector + simulated KG results)
  4. Show the fused context and routing decision

Run:
    python tests/test_example.py

No Neo4j or LLM API key required for this demo (KG results are mocked).
Requires: sentence-transformers, faiss-cpu
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import numpy as np

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Override settings for this demo (no .env file needed) ────────────────────

os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("GROQ_API_KEY", "demo_key")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("EMBEDDING_DIM", "384")
os.environ.setdefault("CHUNK_SIZE", "300")
os.environ.setdefault("CHUNK_OVERLAP", "50")
os.environ.setdefault("VECTOR_TOP_K", "3")
os.environ.setdefault("HYBRID_ALPHA", "0.5")
os.environ.setdefault("RRF_K", "60")
os.environ.setdefault("RERANK_ENABLED", "false")


SEPARATOR = "─" * 70


def section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE DATA (mimics a parsed academic paper)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_PAPER = {
    "paper_id": "attention_2017",
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit"],
    "year": 2017,
    "sections": [
        {
            "heading": "Abstract",
            "content": textwrap.dedent("""\
                The dominant sequence transduction models are based on complex recurrent or
                convolutional neural networks that include an encoder and decoder. The best
                performing models also connect the encoder and decoder through an attention
                mechanism. We propose a new simple network architecture, the Transformer,
                based solely on attention mechanisms, dispensing with recurrence and
                convolutions entirely. Experiments on two machine translation tasks show
                these models to be superior in quality, more parallelizable, and requiring
                significantly less time to train.
            """),
        },
        {
            "heading": "3. Model Architecture",
            "content": textwrap.dedent("""\
                Most competitive neural sequence transduction models have an encoder-decoder
                structure. The encoder maps an input sequence of symbol representations to a
                sequence of continuous representations. Given z, the decoder generates an
                output sequence one element at a time. The Transformer follows this overall
                architecture using stacked self-attention and point-wise, fully connected
                layers for both the encoder and decoder.

                The Multi-Head Attention allows the model to jointly attend to information
                from different representation subspaces at different positions. With a single
                attention head, averaging inhibits this capability.
            """),
        },
        {
            "heading": "4. Why Self-Attention",
            "content": textwrap.dedent("""\
                We compare various aspects of self-attention layers to the recurrent and
                convolutional layers commonly used for mapping one variable-length sequence
                to another sequence of equal length. The total computational complexity per
                layer, the amount of computation that can be parallelized (measured by the
                minimum sequential operations required), and the path length between
                long-range dependencies in the network.

                A self-attention layer connects all positions with a constant number of
                sequentially executed operations, whereas a recurrent layer requires O(n)
                sequential operations.
            """),
        },
    ],
}

SAMPLE_QUERY = "Why does the Transformer use self-attention instead of recurrence?"

# Simulated KG results (would normally come from Neo4j)
SIMULATED_KG_RESULTS = [
    {
        "name": "Transformer",
        "type": "Method",
        "description": "Network architecture based solely on attention mechanisms",
        "relation": "IMPROVES",
        "target": "LSTM",
    },
    {
        "name": "Attention Is All You Need",
        "type": "Paper",
        "year": 2017,
        "relation": "USES_METHOD",
        "method": "Multi-Head Attention",
    },
    {
        "name": "Ashish Vaswani",
        "type": "Author",
        "relation": "AUTHORED_BY",
        "paper": "Attention Is All You Need",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────────────────────

def run_demo():
    print("\n" + "═" * 70)
    print("  Hybrid Graph-RAG System — End-to-End Demo")
    print("═" * 70)

    # ── Step 1: Chunk the paper ───────────────────────────────────────────────
    section("STEP 1: Chunking Paper Sections")

    from pipeline.embedding.chunker import chunk_section

    all_chunks = []
    offset = 0
    for sec in SAMPLE_PAPER["sections"]:
        chunks = chunk_section(
            section_heading=sec["heading"],
            section_text=sec["content"],
            paper_id=SAMPLE_PAPER["paper_id"],
            paper_title=SAMPLE_PAPER["title"],
            authors=SAMPLE_PAPER["authors"],
            year=SAMPLE_PAPER["year"],
            global_chunk_offset=offset,
            chunk_size=300,
            overlap=50,
        )
        all_chunks.extend(chunks)
        offset += len(chunks)
        print(f"  [{sec['heading']}] → {len(chunks)} chunk(s)")

    print(f"\n  Total chunks: {len(all_chunks)}")

    # ── Step 2: Embed ─────────────────────────────────────────────────────────
    section("STEP 2: Generating Embeddings")

    try:
        from pipeline.embedding.embedder import SentenceTransformerEmbedder
        embedder = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
    except ImportError:
        print("  ⚠ sentence-transformers not installed. Using random embeddings for demo.")
        class _FakeEmbedder:
            def embed_texts(self, texts):
                e = np.random.rand(len(texts), 384).astype(np.float32)
                norms = np.linalg.norm(e, axis=1, keepdims=True)
                return e / norms
            def embed_query(self, text):
                e = np.random.rand(384).astype(np.float32)
                return e / np.linalg.norm(e)
        embedder = _FakeEmbedder()

    texts = [c.text for c in all_chunks]
    embeddings = embedder.embed_texts(texts)
    print(f"  Embedding shape: {embeddings.shape}  dtype={embeddings.dtype}")

    # ── Step 3: Index in FAISS ────────────────────────────────────────────────
    section("STEP 3: Building FAISS Index")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            from pipeline.embedding.vector_store import VectorStore
        except ImportError:
            print("  ⚠ faiss-cpu not installed. Skipping index demo.")
            VectorStore = None

        if VectorStore is not None:
            store = VectorStore.load_or_create(tmpdir, dim=384)
            store.add(all_chunks, embeddings)
            store.save()
            print(f"  FAISS index size: {store.size} vectors")

            # ── Step 4: Query Routing ─────────────────────────────────────────
            section("STEP 4: Query Routing")
            print(f"  Query: \"{SAMPLE_QUERY}\"")

            from pipeline.retrieval.query_router import QueryRouter
            router = QueryRouter(use_llm_refinement=False)
            decision = router.route(SAMPLE_QUERY)

            print(f"\n  Routing Decision:")
            print(f"    alpha = {decision.alpha}  (0=KG, 1=vector)")
            print(f"    mode  = {decision.mode}")
            print(f"    reason: {decision.reason}")
            if decision.kg_signals:
                print(f"    KG signals:     {decision.kg_signals}")
            if decision.vec_signals:
                print(f"    Vector signals: {decision.vec_signals}")

            # ── Step 5: Vector Retrieval ──────────────────────────────────────
            section("STEP 5: Vector Retrieval")

            query_vec = embedder.embed_query(SAMPLE_QUERY)
            raw_results = store.search(query_vec, top_k=3)

            from pipeline.retrieval.vector_retriever import RetrievedChunk
            vector_results = []
            for meta, score in raw_results:
                vector_results.append(RetrievedChunk(
                    chunk_id=meta["chunk_id"],
                    paper_id=meta["paper_id"],
                    text=meta["text"],
                    source_section=meta["source_section"],
                    title=meta["title"],
                    authors=meta.get("authors", []),
                    year=meta.get("year"),
                    chunk_index=meta.get("chunk_index", 0),
                    score=score,
                ))

            print(f"\n  Top-{len(vector_results)} Vector Chunks:")
            for i, c in enumerate(vector_results, 1):
                print(f"\n  [{i}] score={c.score:.4f}  section={c.source_section}")
                print(f"      {c.text[:120].strip()!r}...")

            # ── Step 6: Simulated KG Results ──────────────────────────────────
            section("STEP 6: Knowledge Graph Results (Simulated)")
            print("  (In production, these come from Neo4j via LLM-generated Cypher)\n")

            EXAMPLE_CYPHER = textwrap.dedent("""\
                MATCH (m:Method {name: 'Transformer'})
                OPTIONAL MATCH (m)-[:IMPROVES]->(m2:Method)
                OPTIONAL MATCH (p:Paper)-[:USES_METHOD]->(m)
                RETURN m.name, m.description, m2.name AS improves, p.name AS paper
                LIMIT 10
            """)
            print(f"  Cypher Query:\n  {EXAMPLE_CYPHER.strip()}")

            for r in SIMULATED_KG_RESULTS:
                print(f"  → {r}")

            # ── Step 7: RRF Fusion ────────────────────────────────────────────
            section("STEP 7: RRF Fusion")

            from pipeline.retrieval.fusion import reciprocal_rank_fusion, build_llm_context
            fused = reciprocal_rank_fusion(
                vector_results, SIMULATED_KG_RESULTS,
                alpha=decision.alpha, k=60,
            )

            print(f"\n  Fused ranking ({len(fused)} items):")
            for i, item in enumerate(fused, 1):
                label = item.title or item.item_id
                print(f"  [{i}] source={item.source:<8}  rrf={item.rrf_score:.5f}  id={label[:40]}")

            context_block = build_llm_context(
                fused=fused,
                query=SAMPLE_QUERY,
                cypher=EXAMPLE_CYPHER,
                max_items=5,
            )

            # ── Step 8: LLM Prompt Preview ────────────────────────────────────
            section("STEP 8: LLM Prompt Context (would be sent to LLM)")
            print()
            print(context_block[:1200] + ("…" if len(context_block) > 1200 else ""))

            # ── Summary ───────────────────────────────────────────────────────
            section("SUMMARY")
            print(f"  Query:          {SAMPLE_QUERY!r}")
            print(f"  Routing:        alpha={decision.alpha}  mode={decision.mode}")
            print(f"  Vector chunks:  {len(vector_results)} retrieved")
            print(f"  KG records:     {len(SIMULATED_KG_RESULTS)} retrieved")
            print(f"  Fused items:    {len(fused)}")
            print(f"\n  ✅ Demo complete! In production, the fused context is sent")
            print(f"     to the LLM (Groq/Ollama) for final answer generation.")
        else:
            print("\n  Skipping vector retrieval — faiss-cpu not installed.")

    print("\n" + "═" * 70 + "\n")


if __name__ == "__main__":
    run_demo()
