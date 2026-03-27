"""
Shared LLM provider selection for SCOUT agents.

Supports:
- Groq-hosted models (default)
- Local Ollama models for open-source mode
"""

from core.config import CONFIG


def get_chat_llm(temperature: float = 0.0):
    provider = (CONFIG.LLM_PROVIDER or "groq").lower()

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama

            return ChatOllama(
                model=CONFIG.OLLAMA_MODEL,
                base_url=CONFIG.OLLAMA_BASE_URL,
                temperature=temperature,
            )
        except Exception:
            # Fall back to Groq if Ollama integration is unavailable.
            pass

    from langchain_groq import ChatGroq

    return ChatGroq(
        model=CONFIG.LLM_MODEL,
        temperature=temperature,
        groq_api_key=CONFIG.GROQ_API_KEY,
    )
