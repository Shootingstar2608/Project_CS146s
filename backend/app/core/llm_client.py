"""
Core: LLM Client Factory.

Returns a LangChain chat model based on LLM_PROVIDER env var.
Supports: groq | ollama
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """
    Factory: returns a cached LangChain chat model.

    Reads LLM_PROVIDER from settings:
      - "groq"   → ChatGroq (requires GROQ_API_KEY)
      - "ollama" → ChatOllama (requires local Ollama running)
    """
    from app.config import get_settings

    cfg = get_settings()
    provider = cfg.llm_provider.lower().strip()

    if provider == "groq":
        from langchain_groq import ChatGroq

        logger.info("LLM: ChatGroq — model=%s", cfg.llm_model)
        return ChatGroq(
            model=cfg.llm_model,
            api_key=cfg.groq_api_key,
            temperature=0.0,
            max_retries=3,
        )

    if provider == "ollama":
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError as exc:
            raise ImportError(
                "langchain-community is required for Ollama. "
                "Run: pip install langchain-community"
            ) from exc

        logger.info(
            "LLM: ChatOllama — model=%s  base_url=%s",
            cfg.llm_model,
            cfg.ollama_base_url,
        )
        return ChatOllama(
            model=cfg.llm_model,
            base_url=cfg.ollama_base_url,
            temperature=0.0,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Supported: groq, ollama"
    )
