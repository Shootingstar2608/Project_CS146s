"""
Tests: Hybrid Retrieval Layer

Tests query router, vector retriever (mocked FAISS), and RRF fusion.
Does not require a running Neo4j or LLM.
"""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ── Query Router tests ────────────────────────────────────────────────────────

class TestQueryRouter:
    @pytest.fixture
    def router(self):
        from pipeline.retrieval.query_router import QueryRouter
        return QueryRouter(use_llm_refinement=False)

    def test_kg_heavy_author_query(self, router):
        decision = router.route("Papers by Vaswani et al. on Transformers")
        assert decision.alpha < 0.5
        assert decision.mode in ("kg", "hybrid")

    def test_kg_heavy_comparison_query(self, router):
        decision = router.route('Compare "BERT" vs "GPT-2" on SQuAD')
        assert decision.alpha < 0.6

    def test_vector_heavy_conceptual_query(self, router):
        decision = router.route("What are the main challenges in neural machine translation?")
        assert decision.alpha > 0.5
        assert decision.mode in ("vector", "hybrid")

    def test_vector_heavy_summary_query(self, router):
        decision = router.route("Summarize recent trends in large language models")
        assert decision.alpha > 0.5

    def test_returns_routing_decision(self, router):
        from pipeline.retrieval.query_router import RoutingDecision
        result = router.route("What datasets are used?")
        assert isinstance(result, RoutingDecision)
        assert 0.0 <= result.alpha <= 1.0
        assert result.mode in ("kg", "vector", "hybrid")
        assert isinstance(result.reason, str)

    def test_alpha_in_valid_range(self, router):
        queries = [
            "List all papers by Hinton",
            "Explain what attention mechanism is",
            "BERT evaluated on GLUE",
            "What are the limitations of current approaches?",
        ]
        for q in queries:
            d = router.route(q)
            assert 0.0 <= d.alpha <= 1.0, f"alpha out of range for: {q}"


class TestExtractQueryEntities:
    def test_et_al_pattern(self):
        from pipeline.retrieval.graph_retriever import extract_query_entities
        entities = extract_query_entities("Vaswani et al. proposed the Transformer")
        assert any("Vaswani" in e for e in entities)

    def test_quoted_string(self):
        from pipeline.retrieval.graph_retriever import extract_query_entities
        entities = extract_query_entities('Papers using "BERT" on "SQuAD"')
        assert "BERT" in entities
        assert "SQuAD" in entities

    def test_uppercase_token(self):
        from pipeline.retrieval.graph_retriever import extract_query_entities
        entities = extract_query_entities("How does GPT perform on NLP tasks?")
        assert "GPT" in entities or "NLP" in entities

    def test_no_entities(self):
        from pipeline.retrieval.graph_retriever import extract_query_entities
        entities = extract_query_entities("What are the main challenges?")
        # Falls back to LLM — stub it out
        assert isinstance(entities, list)


# ── Vector Retriever tests (mocked) ──────────────────────────────────────────

class TestVectorRetriever:
    def _make_mock_store(self, n_results: int = 3):
        """Build a mock VectorStore with n_results pre-loaded."""
        mock_store = MagicMock()
        mock_store.size = n_results

        fake_meta = [
            {
                "chunk_id": f"c{i}",
                "paper_id": f"p{i}",
                "text": f"Chunk text {i}",
                "source_section": "Introduction",
                "title": f"Paper {i}",
                "authors": [f"Author {i}"],
                "year": 2020 + i,
                "chunk_index": i,
            }
            for i in range(n_results)
        ]
        mock_store.search.return_value = [(m, 0.9 - i * 0.1) for i, m in enumerate(fake_meta)]
        return mock_store

    def _make_mock_embedder(self):
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = np.random.rand(384).astype(np.float32)
        return mock_emb

    def test_returns_retrieved_chunks(self):
        from pipeline.retrieval.vector_retriever import retrieve_chunks, RetrievedChunk

        with (
            patch("pipeline.retrieval.vector_retriever.get_embedder", return_value=self._make_mock_embedder()),
            patch("pipeline.retrieval.vector_retriever.get_vector_store", return_value=self._make_mock_store(3)),
        ):
            results = retrieve_chunks("What is BERT?", top_k=3)

        assert len(results) == 3
        assert all(isinstance(r, RetrievedChunk) for r in results)

    def test_scores_descending(self):
        from pipeline.retrieval.vector_retriever import retrieve_chunks

        with (
            patch("pipeline.retrieval.vector_retriever.get_embedder", return_value=self._make_mock_embedder()),
            patch("pipeline.retrieval.vector_retriever.get_vector_store", return_value=self._make_mock_store(3)),
        ):
            results = retrieve_chunks("query", top_k=3)

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_store_returns_empty(self):
        from pipeline.retrieval.vector_retriever import retrieve_chunks

        mock_store = MagicMock()
        mock_store.size = 0

        with (
            patch("pipeline.retrieval.vector_retriever.get_embedder", return_value=self._make_mock_embedder()),
            patch("pipeline.retrieval.vector_retriever.get_vector_store", return_value=mock_store),
        ):
            results = retrieve_chunks("query")

        assert results == []

    def test_chunk_metadata_preserved(self):
        from pipeline.retrieval.vector_retriever import retrieve_chunks

        with (
            patch("pipeline.retrieval.vector_retriever.get_embedder", return_value=self._make_mock_embedder()),
            patch("pipeline.retrieval.vector_retriever.get_vector_store", return_value=self._make_mock_store(2)),
        ):
            results = retrieve_chunks("test", top_k=2)

        assert results[0].title == "Paper 0"
        assert results[0].year == 2020


# ── Fusion / RRF tests ────────────────────────────────────────────────────────

class TestRRFFusion:
    @pytest.fixture
    def sample_vector_results(self):
        from pipeline.retrieval.vector_retriever import RetrievedChunk
        return [
            RetrievedChunk(
                chunk_id=f"vc{i}", paper_id=f"p{i}", text=f"Chunk {i}",
                source_section="Intro", title=f"Paper {i}",
                authors=[], year=2020+i, chunk_index=i, score=0.9 - i * 0.1,
            )
            for i in range(3)
        ]

    @pytest.fixture
    def sample_kg_results(self):
        return [
            {"name": f"KG Entity {i}", "description": f"Desc {i}"}
            for i in range(2)
        ]

    def test_fused_length(self, sample_vector_results, sample_kg_results):
        from pipeline.retrieval.fusion import reciprocal_rank_fusion
        fused = reciprocal_rank_fusion(sample_vector_results, sample_kg_results, alpha=0.5)
        assert len(fused) == 5  # 3 vector + 2 kg (no overlap)

    def test_scores_descending(self, sample_vector_results, sample_kg_results):
        from pipeline.retrieval.fusion import reciprocal_rank_fusion
        fused = reciprocal_rank_fusion(sample_vector_results, sample_kg_results, alpha=0.5)
        scores = [r.rrf_score for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_pure_vector_alpha_1(self, sample_vector_results, sample_kg_results):
        from pipeline.retrieval.fusion import reciprocal_rank_fusion
        fused = reciprocal_rank_fusion(sample_vector_results, sample_kg_results, alpha=1.0)
        # All KG items should have 0 contribution
        kg_items = [r for r in fused if r.source == "kg"]
        for item in kg_items:
            assert item.rrf_score == 0.0

    def test_pure_kg_alpha_0(self, sample_vector_results, sample_kg_results):
        from pipeline.retrieval.fusion import reciprocal_rank_fusion
        fused = reciprocal_rank_fusion(sample_vector_results, sample_kg_results, alpha=0.0)
        vec_items = [r for r in fused if r.source == "vector"]
        for item in vec_items:
            assert item.rrf_score == 0.0

    def test_context_builder_non_empty(self, sample_vector_results, sample_kg_results):
        from pipeline.retrieval.fusion import reciprocal_rank_fusion, build_llm_context
        fused = reciprocal_rank_fusion(sample_vector_results, sample_kg_results, alpha=0.5)
        context = build_llm_context(fused, "test query", cypher="MATCH (p:Paper) RETURN p")
        assert "Semantic Context" in context or "Structured Facts" in context

    def test_empty_inputs(self):
        from pipeline.retrieval.fusion import reciprocal_rank_fusion
        fused = reciprocal_rank_fusion([], [], alpha=0.5)
        assert fused == []


# ── Reranker tests ────────────────────────────────────────────────────────────

class TestReranker:
    def test_disabled_returns_original(self):
        from pipeline.retrieval.reranker import rerank
        from pipeline.retrieval.fusion import FusedResult

        candidates = [
            FusedResult(item_id=f"i{i}", source="vector", rrf_score=0.9 - i * 0.1)
            for i in range(3)
        ]

        with patch("pipeline.retrieval.reranker.get_settings") as mock_cfg:
            mock_cfg.return_value.rerank_enabled = False
            result = rerank("query", candidates)

        assert result == candidates

    def test_empty_candidates(self):
        from pipeline.retrieval.reranker import rerank
        result = rerank("query", [])
        assert result == []
