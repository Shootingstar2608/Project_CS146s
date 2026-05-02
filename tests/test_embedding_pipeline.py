"""
Tests: Embedding Pipeline

Tests the chunker, embedder, and FAISS vector store without requiring
a running Neo4j or LLM (fully offline).
"""

from __future__ import annotations

import os
import tempfile
import numpy as np
import pytest


# ── Chunker tests ─────────────────────────────────────────────────────────────

class TestChunkText:
    def test_empty_input(self):
        from pipeline.embedding.chunker import chunk_text
        assert chunk_text("") == []

    def test_short_text_single_chunk(self):
        from pipeline.embedding.chunker import chunk_text
        text = "Short text under limit."
        chunks = chunk_text(text, chunk_size=512, overlap=64)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_overlap_creates_multiple_chunks(self):
        from pipeline.embedding.chunker import chunk_text
        # 600-char text with chunk_size=400, overlap=50
        text = "A" * 600
        chunks = chunk_text(text, chunk_size=400, overlap=50)
        assert len(chunks) == 2
        # Second chunk starts at 400 - 50 = 350, so it overlaps
        assert len(chunks[0]) == 400
        assert len(chunks[1]) == 600 - 350  # 250 chars

    def test_no_empty_chunks(self):
        from pipeline.embedding.chunker import chunk_text
        text = "word " * 200  # 1000 chars
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert all(len(c) > 0 for c in chunks)


class TestChunkSection:
    def test_output_is_chunk_objects(self):
        from pipeline.embedding.chunker import chunk_section, Chunk
        chunks = chunk_section(
            section_heading="Introduction",
            section_text="This paper proposes a novel method for NLP.",
            paper_id="paper_001",
            paper_title="Test Paper",
            authors=["Alice", "Bob"],
            year=2024,
        )
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_id_is_deterministic(self):
        from pipeline.embedding.chunker import chunk_section
        text = "Deterministic content for testing."
        c1 = chunk_section("Intro", text, "paper_x")
        c2 = chunk_section("Intro", text, "paper_x")
        assert c1[0].chunk_id == c2[0].chunk_id

    def test_section_heading_prepended(self):
        from pipeline.embedding.chunker import chunk_section
        chunks = chunk_section(
            section_heading="Methods",
            section_text="We use attention mechanism.",
            paper_id="p1",
        )
        assert "[Methods]" in chunks[0].text

    def test_global_offset(self):
        from pipeline.embedding.chunker import chunk_section
        chunks = chunk_section(
            section_heading="Results",
            section_text="Results text " * 50,
            paper_id="p2",
            global_chunk_offset=10,
        )
        assert chunks[0].chunk_index == 10

    def test_metadata_preserved(self):
        from pipeline.embedding.chunker import chunk_section
        chunks = chunk_section(
            "Abstract",
            "Text " * 10,
            "p3",
            paper_title="My Paper",
            authors=["Dr. Smith"],
            year=2023,
        )
        c = chunks[0]
        assert c.title == "My Paper"
        assert "Dr. Smith" in c.authors
        assert c.year == 2023

    def test_to_dict_roundtrip(self):
        from pipeline.embedding.chunker import chunk_section
        chunks = chunk_section("Sec", "Some text.", "p4")
        d = chunks[0].to_dict()
        assert "chunk_id" in d
        assert "text" in d
        assert "paper_id" in d


# ── Embedder tests ────────────────────────────────────────────────────────────

class TestSentenceTransformerEmbedder:
    @pytest.fixture(scope="class")
    def embedder(self):
        pytest.importorskip("sentence_transformers")
        from pipeline.embedding.embedder import SentenceTransformerEmbedder
        return SentenceTransformerEmbedder("all-MiniLM-L6-v2")

    def test_embed_texts_shape(self, embedder):
        texts = ["Hello world", "Attention is all you need"]
        result = embedder.embed_texts(texts)
        assert result.shape == (2, 384)
        assert result.dtype == np.float32

    def test_embed_texts_empty(self, embedder):
        result = embedder.embed_texts([])
        assert result.shape[0] == 0

    def test_embed_query_shape(self, embedder):
        q = embedder.embed_query("What is BERT?")
        assert q.shape == (384,)

    def test_embeddings_are_l2_normalized(self, embedder):
        texts = ["Test sentence for normalization check."]
        emb = embedder.embed_texts(texts)
        norms = np.linalg.norm(emb, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)


# ── VectorStore tests ─────────────────────────────────────────────────────────

class TestVectorStore:
    @pytest.fixture
    def tmp_store(self, tmp_path):
        pytest.importorskip("faiss")
        from pipeline.embedding.vector_store import VectorStore
        return VectorStore.load_or_create(str(tmp_path / "faiss"), dim=4)

    @pytest.fixture
    def sample_chunks(self):
        from pipeline.embedding.chunker import Chunk
        return [
            Chunk(
                chunk_id=f"c{i}",
                paper_id="p1",
                text=f"Chunk text {i}",
                source_section="Intro",
                title="Paper A",
                authors=["Author"],
                year=2023,
                chunk_index=i,
            )
            for i in range(5)
        ]

    @pytest.fixture
    def sample_embeddings(self):
        emb = np.random.rand(5, 4).astype(np.float32)
        # L2-normalize
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        return emb / norms

    def test_initial_size_zero(self, tmp_store):
        assert tmp_store.size == 0

    def test_add_and_size(self, tmp_store, sample_chunks, sample_embeddings):
        tmp_store.add(sample_chunks, sample_embeddings)
        assert tmp_store.size == 5

    def test_search_returns_top_k(self, tmp_store, sample_chunks, sample_embeddings):
        tmp_store.add(sample_chunks, sample_embeddings)
        query = sample_embeddings[0]  # identical → top hit
        results = tmp_store.search(query, top_k=3)
        assert len(results) == 3
        meta, score = results[0]
        assert score > 0.9  # near-identical vector → near 1.0 cosine

    def test_search_returns_chunk_metadata(self, tmp_store, sample_chunks, sample_embeddings):
        tmp_store.add(sample_chunks, sample_embeddings)
        results = tmp_store.search(sample_embeddings[2], top_k=1)
        meta, _ = results[0]
        assert "chunk_id" in meta
        assert "text" in meta

    def test_search_empty_store(self, tmp_store):
        query = np.random.rand(4).astype(np.float32)
        results = tmp_store.search(query, top_k=5)
        assert results == []

    def test_save_and_reload(self, tmp_path, sample_chunks, sample_embeddings):
        pytest.importorskip("faiss")
        from pipeline.embedding.vector_store import VectorStore
        store = VectorStore.load_or_create(str(tmp_path / "faiss2"), dim=4)
        store.add(sample_chunks, sample_embeddings)
        store.save()

        # Reload
        store2 = VectorStore.load_or_create(str(tmp_path / "faiss2"), dim=4)
        assert store2.size == 5

    def test_shape_mismatch_raises(self, tmp_store, sample_chunks):
        wrong_shape = np.random.rand(5, 8).astype(np.float32)
        with pytest.raises(AssertionError):
            tmp_store.add(sample_chunks, wrong_shape)
