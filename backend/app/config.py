"""
Application Configuration — Pydantic-Settings.

Reads from environment / .env file.
All new hybrid-retrieval settings are added here.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = Field("groq", description="groq | ollama")
    llm_model: str = Field("llama-3.3-70b-versatile")
    groq_api_key: str = Field("", description="Groq API key (leave blank for Ollama)")
    ollama_base_url: str = Field("http://localhost:11434")

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri: str = Field("bolt://localhost:7687")
    neo4j_user: str = Field("neo4j")
    neo4j_password: str = Field("graphrag_secret_2024")

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    postgres_url: str = Field(
        "postgresql+asyncpg://postgres:postgres_secret_2024@localhost:5432/graphrag"
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379/0")

    # ── Application ───────────────────────────────────────────────────────────
    backend_host: str = Field("0.0.0.0")
    backend_port: int = Field(8000)
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:80"]
    )
    upload_dir: str = Field("/app/data/uploads")
    max_upload_size_mb: int = Field(50)

    # ── Vector / Embedding (NEW) ──────────────────────────────────────────────
    vector_store_path: str = Field(
        "data/faiss",
        description="Directory where FAISS index files are persisted",
    )
    embedding_model: str = Field(
        "all-MiniLM-L6-v2",
        description="SentenceTransformers model name (or swap to OpenAI)",
    )
    embedding_dim: int = Field(
        384, description="Embedding dimension — must match embedding_model"
    )
    chunk_size: int = Field(
        512, description="Max characters per text chunk"
    )
    chunk_overlap: int = Field(
        64, description="Overlap characters between consecutive chunks"
    )
    vector_top_k: int = Field(
        5, description="Number of vector candidates to retrieve"
    )

    # ── Hybrid Fusion (NEW) ───────────────────────────────────────────────────
    hybrid_alpha: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Default fusion weight. 0 = pure KG, 1 = pure vector. "
            "Overridden per-query by the query router."
        ),
    )
    rrf_k: int = Field(60, description="Constant k for Reciprocal Rank Fusion")

    # ── Re-ranking (Bonus, NEW) ───────────────────────────────────────────────
    rerank_enabled: bool = Field(False)
    rerank_model: str = Field("cross-encoder/ms-marco-MiniLM-L-6-v2")
    rerank_top_n: int = Field(5)

    @field_validator("vector_store_path", mode="before")
    @classmethod
    def _expand_path(cls, v: str) -> str:
        return str(Path(v).expanduser())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
