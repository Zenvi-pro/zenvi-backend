"""
Ollama provider — LangChain ChatOllama for local models.
Ported from zenvi-core.
"""

from logger import log


def is_available(model_id, settings):
    return model_id.startswith("ollama/")


def build_chat_model(model_id, settings):
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        log.warning("langchain-ollama not installed")
        return None

    base_url = (settings.get("ollama-base-url") or "http://localhost:11434").strip()
    model_name = model_id.split("/", 1)[-1] if "/" in model_id else model_id
    return ChatOllama(model=model_name, base_url=base_url, temperature=0.2)
