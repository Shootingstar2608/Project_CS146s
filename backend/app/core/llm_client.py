from functools import lru_cache
from langchain_groq import ChatGroq
from langchain_community.chat_models import ChatOllama
from backend.app.config import settings

@lru_cache()
def get_llm():
    """
    Factory function to get LLM client based on provider settings.
    """
    if settings.LLM_PROVIDER == "groq":
        return ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=settings.LLM_MODEL,
            temperature=0,
        )
    elif settings.LLM_PROVIDER == "ollama":
        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
