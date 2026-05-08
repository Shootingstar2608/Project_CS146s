from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os

class Settings(BaseSettings):
    # LLM Settings
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Neo4j Settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # PostgreSQL Settings
    POSTGRES_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/graphrag"

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # App Settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
