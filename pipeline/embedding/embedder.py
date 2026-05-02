"""
Embedding Pipeline: Embedder

Wraps SentenceTransformers as a lazy singleton.
Swap-in path: replace the inner implementation with OpenAI embeddings
by subclassing BaseEmbedder and overriding embed_texts().

Model: all-MiniLM-L6-v2 (384-dim, ~80 MB, MIT license)
  - Fast, runs on CPU without GPU
  - 512-token context window aligns perfectly with our chunk_size
"""

from __future__ import annotations

import logging
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


@lru_cache(maxsize=1)
def get_embedder() -> BaseEmbedder:
    """
    Return the cached singleton embedder.

    Reads EMBEDDING_MODEL from settings so the model can be changed
    without touching application code.
    """
    from app.config import get_settings
    cfg = get_settings()
    return SentenceTransformerEmbedder(model_name=cfg.embedding_model)
