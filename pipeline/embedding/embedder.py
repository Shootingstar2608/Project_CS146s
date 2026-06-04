"""
Embedding Pipeline: Embedder

Uses a deterministic hashing embedder by default so the demo can run in
Docker without downloading large ML models. If sentence-transformers is
installed and EMBEDDING_MODEL is set to a non-hashing model name, the local
transformer embedder remains available.
"""

from __future__ import annotations

import logging
import hashlib
import re
import numpy as np
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    """Abstract embedder — swap implementations without touching callers."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Return (N, D) float32 array."""

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query string → (D,) float32 array."""
        return self.embed_texts([text])[0]


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local SentenceTransformer model (no API key required)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required. "
                "Run: pip install sentence-transformers"
            ) from exc

        logger.info("Loading SentenceTransformer: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts in batch.

        Returns:
            L2-normalised float32 array of shape (len(texts), embedding_dim).
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        embeddings = self._model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,  # L2-norm for cosine similarity via dot product
            convert_to_numpy=True,
        )
        return embeddings.astype(np.float32)


class HashingEmbedder(BaseEmbedder):
    """Small deterministic bag-of-words embedder for local/demo vector search."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        rows = np.zeros((len(texts), self._dim), dtype=np.float32)
        for row_index, text in enumerate(texts):
            tokens = re.findall(r"[A-Za-z0-9_]+", text.casefold())
            for token in tokens:
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self._dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                rows[row_index, bucket] += sign

            norm = np.linalg.norm(rows[row_index])
            if norm > 0:
                rows[row_index] /= norm

        return rows


@lru_cache(maxsize=1)
def get_embedder() -> BaseEmbedder:
    """
    Return the cached singleton embedder.

    Reads EMBEDDING_MODEL from settings so the model can be changed
    without touching application code.
    """
    from app.config import get_settings
    cfg = get_settings()
    if cfg.embedding_model.lower() in {"hash", "hashing", "local-hash"}:
        return HashingEmbedder()
    return SentenceTransformerEmbedder(model_name=cfg.embedding_model)
