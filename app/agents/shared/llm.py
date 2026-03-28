"""
LLM singleton factory.

The LLM is intentionally lazy-initialized — if OPENAI_API_KEY is not set,
get_llm() returns None and nodes skip the LLM call gracefully.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_llm_instance = None


def get_llm(settings=None):
    """
    Returns a ChatOpenAI instance, or None if OPENAI_API_KEY is not set.
    Singleton: same instance reused across all requests.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    if settings is None:
        from app.config import get_settings
        settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set — LLM calls will be skipped")
        return None

    try:
        from langchain_openai import ChatOpenAI
        _llm_instance = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
            max_tokens=500,
        )
        logger.info("ChatOpenAI initialised (model=%s)", settings.openai_model)
        return _llm_instance
    except Exception as e:
        logger.error("Failed to initialise LLM: %s", e)
        return None
