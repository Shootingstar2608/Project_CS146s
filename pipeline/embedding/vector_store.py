"""
Embedding Pipeline: FAISS Vector Store

Provides an in-process, disk-persistent FAISS index with a parallel
metadata store (JSON) so we can recover full Chunk objects from search results.

Index type: IndexFlatIP (exact inner product)
  - L2-normalised embeddings → cosine similarity via dot product
  - No approximation artefacts; fast enough for <1M chunks
  - For >1M chunks, swap to IndexIVFFlat (add nlist param + train step)

File layout (all under VECTOR_STORE_PATH):
  chunks.index   ← FAISS binary index
  chunks.meta    ← JSON list of Chunk.to_dict() in insertion order
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import List, Tuple

import numpy as np

from pipeline.embedding.chunker import Chunk

logger = logging.getLogger(__name__)

# Guards every mutation of the shared VectorStore singleton (add/delete + save).
# IndexFlatIP rebuilds and the parallel metadata list are not concurrency-safe,
# so ingestion and deletion must serialise through this lock.
vector_store_lock = Lock()

_INDEX_FILE = "chunks.index"
_META_FILE = "chunks.meta"


class VectorStore:
    """
    FAISS-backed vector store with metadata sidecar.

    Usage::

        store = VectorStore.load_or_create("/data/faiss", dim=384)
        store.add(chunks, embeddings)
        store.save()

        results = store.search(query_embedding, top_k=5)
    """

    def __init__(self, index, metadata: List[dict], dim: int, store_path: str) -> None:
        self._index = index
        self._metadata = metadata  # parallel list: metadata[i] ↔ index vector i
        self._dim = dim
        self._store_path = Path(store_path)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def load_or_create(cls, store_path: str, dim: int = 384) -> "VectorStore":
        """
        Load existing index from disk or create a fresh one.

        Args:
            store_path: Directory where index files are stored.
            dim:        Embedding dimensionality.
        """
        try:
            import faiss
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is required. Run: pip install faiss-cpu"
            ) from exc

        path = Path(store_path)
        path.mkdir(parents=True, exist_ok=True)

        index_file = path / _INDEX_FILE
        meta_file = path / _META_FILE

        if index_file.exists() and meta_file.exists():
            logger.info("Loading FAISS index from %s", path)
            index = faiss.read_index(str(index_file))
            with open(meta_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            logger.info("Loaded %d vectors", index.ntotal)
        else:
            logger.info("Creating new FAISS IndexFlatIP (dim=%d)", dim)
            index = faiss.IndexFlatIP(dim)
            metadata = []

        return cls(index, metadata, dim, store_path)

    # ── Write operations ──────────────────────────────────────────────────────

    def add(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        """
        Add chunks and their embeddings to the index.

        Args:
            chunks:     List of Chunk objects.
            embeddings: float32 array of shape (len(chunks), dim).
        """
        if len(chunks) == 0:
            return

        assert embeddings.shape == (len(chunks), self._dim), (
            f"Shape mismatch: expected ({len(chunks)}, {self._dim}), "
            f"got {embeddings.shape}"
        )

        self._index.add(embeddings.astype(np.float32))
        self._metadata.extend(c.to_dict() for c in chunks)
        logger.debug("Added %d chunks. Total: %d", len(chunks), self._index.ntotal)

    def save(self) -> None:
        """Persist index and metadata to disk."""
        import faiss

        path = self._store_path
        path.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(path / _INDEX_FILE))
        with open(path / _META_FILE, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

        logger.info("FAISS index saved (%d vectors) to %s", self._index.ntotal, path)

    def delete_by_paper_id(self, paper_id: str) -> int:
        """
        Delete all vectors whose chunk metadata matches ``paper_id``.

        ``IndexFlatIP`` does not support safe IDSelector-based removal against a
        parallel metadata list (its ``remove_ids`` would renumber FAISS rows but
        leave ``self._metadata`` misaligned). Instead we reconstruct every vector,
        drop the target paper's rows, and rebuild the index from scratch so FAISS
        row order and the metadata list stay aligned.

        Callers must hold :data:`vector_store_lock` and call :meth:`save`
        afterwards to persist the change.

        Returns:
            Number of chunk vectors removed (0 if the paper had no chunks).
        """
        import faiss

        target = str(paper_id)
        total = int(self._index.ntotal)
        if total == 0:
            return 0

        if len(self._metadata) != total:
            raise ValueError(
                f"VectorStore metadata length ({len(self._metadata)}) "
                f"differs from FAISS ntotal ({total}) — index is corrupt."
            )

        remove_mask = [str(m.get("paper_id", "")) == target for m in self._metadata]
        deleted_count = int(sum(remove_mask))
        if deleted_count == 0:
            return 0

        # Reconstruct all raw vectors, then keep only the rows to retain.
        all_vectors = np.empty((total, self._dim), dtype=np.float32)
        self._index.reconstruct_n(0, total, all_vectors)
        keep_mask = np.array([not r for r in remove_mask], dtype=bool)
        kept_vectors = np.ascontiguousarray(all_vectors[keep_mask].astype(np.float32))
        kept_metadata = [m for m, r in zip(self._metadata, remove_mask) if not r]

        new_index = faiss.IndexFlatIP(self._dim)
        if kept_vectors.shape[0] > 0:
            new_index.add(kept_vectors)

        self._index = new_index
        self._metadata = kept_metadata
        logger.info(
            "FAISS: removed %d chunks for paper_id=%s; %d vectors remain.",
            deleted_count,
            target,
            self._index.ntotal,
        )
        return deleted_count

    # ── Read operations ───────────────────────────────────────────────────────

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[Tuple[dict, float]]:
        """
        Retrieve top-k nearest chunks.

        Args:
            query_embedding: 1-D float32 array of shape (dim,).
            top_k:           Number of results to return.

        Returns:
            List of (chunk_metadata_dict, cosine_score) sorted by score desc.
        """
        if self._index.ntotal == 0:
            logger.warning("VectorStore is empty — returning no results.")
            return []

        q = query_embedding.reshape(1, -1).astype(np.float32)
        actual_k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(q, actual_k)

        results: List[Tuple[dict, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                continue
            meta = self._metadata[idx]
            results.append((meta, float(score)))

        return results

    @property
    def size(self) -> int:
        """Total number of indexed vectors."""
        return self._index.ntotal


# ── Module-level singleton ────────────────────────────────────────────────────

_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Lazy-load the global VectorStore singleton."""
    global _store
    if _store is None:
        from app.config import get_settings
        cfg = get_settings()
        _store = VectorStore.load_or_create(
            store_path=cfg.faiss_index_path,
            dim=getattr(cfg, "embedding_dim", 384),
        )
    return _store
