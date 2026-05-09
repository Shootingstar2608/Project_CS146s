"""
LLM Client — Factory function trả về LangChain chat model.

Hỗ trợ hai provider:
  - groq   : ChatGroq (API key từ GROQ_API_KEY, miễn phí tier)
  - ollama : ChatOllama (local, không cần API key)

Dùng lru_cache để tránh khởi tạo lại model mỗi request.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """
    Return a cached LangChain chat model instance.

    Provider được xác định qua biến môi trường LLM_PROVIDER:
      - "groq"   → ChatGroq  (requires GROQ_API_KEY)
      - "ollama" → ChatOllama (requires Ollama running locally)
    """
    from app.config import get_settings

    cfg = get_settings()
    provider = cfg.llm_provider.lower()

    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise ImportError(
                "langchain-groq is required for the 'groq' provider. "
                "Run: pip install langchain-groq"
            ) from exc

        if not cfg.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )

        logger.info("Initialising LLM: ChatGroq / model=%s", cfg.llm_model)
        return ChatGroq(
            api_key=cfg.groq_api_key,
            model=cfg.llm_model,
            temperature=0,
            max_retries=3,
        )

    if provider == "ollama":
        try:
            from langchain_community.chat_models.ollama import ChatOllama
        except ImportError:
            try:
                from langchain_ollama import ChatOllama  # type: ignore[import]
            except ImportError as exc:
                raise ImportError(
                    "For the 'ollama' provider, install either:\n"
                    "  pip install langchain-community  or  pip install langchain-ollama"
                ) from exc

        logger.info(
            "Initialising LLM: ChatOllama / model=%s / base_url=%s",
            cfg.llm_model,
            cfg.ollama_base_url,
        )
        return ChatOllama(
            model=cfg.llm_model,
            base_url=cfg.ollama_base_url,
            temperature=0,
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER: {cfg.llm_provider!r}. "
        "Supported values: 'groq', 'ollama'."
    )
