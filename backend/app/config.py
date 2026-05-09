"""
Application Settings — đọc từ .env qua pydantic-settings.

Tất cả biến môi trường đều có giá trị mặc định an toàn cho dev.
Trong production, hãy tạo file .env từ .env.example và override.
"""

from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────────────────────
    groq_api_key: str = ""
    llm_provider: str = "groq"          # "groq" | "ollama"
    llm_model: str = "llama-3.3-70b-versatile"

    # Ollama (fallback local)
    ollama_base_url: str = "http://host.docker.internal:11434"

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "graphrag_secret_2024"

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    postgres_user: str = "postgres"
    postgres_password: str = "postgres_secret_2024"
    postgres_db: str = "graphrag"
    postgres_url: str = (
        "postgresql+asyncpg://postgres:postgres_secret_2024@localhost:5432/graphrag"
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Application ───────────────────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:80",
        "http://localhost",
    ]

    # ── File upload ───────────────────────────────────────────────────────────
    upload_dir: str = "/app/data/uploads"
    max_upload_size_mb: int = 50

    # ── Embedding / Vector Store ──────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    faiss_index_path: str = "/app/data/faiss_index"
    chunk_size: int = 512
    chunk_overlap: int = 64

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
